import sys
from pathlib import Path
script_path = Path(__file__).resolve()
project_root = script_path.parents[1]
sys.path.insert(0, str(project_root))
from server_wsl.src.core.logger_config import logger
import os
import pyaudio
import wave
import socket
import time
import keyboard
from configparser import ConfigParser
from playsound import playsound

# --- Конфигурация ---
config_file = r'config.ini'
config = ConfigParser()
config.read(config_file)

# --- Аудио настройки ---
SAMPLE_RATE = int(config['AUDIO']['sample_rate'])
CHANNELS = int(config['AUDIO']['channels'])
FORMAT = pyaudio.paInt16
FRAMES_PER_BUFFER = int(config['AUDIO']['frames_per_buffer'])
WAVE_OUTPUT_FILENAME = str(Path(__file__).resolve().parents[1] / "server_wsl" / "temp_audio" / "received" / "recorder_audio.wav")
WAVE_TO_PLAY =Path(__file__).resolve().parents[1] / "server_wsl" / "temp_audio" / "pronounced"


# --- Сетевые настройки ---
HOST = config['SERVER']['host']
PORT = int(config['SERVER']['port'])

# --- Глобальные переменные для управления записью ---
is_recording = False
can_start_new_recording = True  # Флаг, разрешающий начать новую запись
audio_frames = []
p = None
stream = None


def audio_recorder():
    """
    Функция, которая выполняется в отдельном потоке.
    Слушает микрофон, но записывает данные только когда is_recording=True.
    """
    global audio_frames, p, stream

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=FRAMES_PER_BUFFER)

    logger.info("✓ Аудиосистема готова. Нажмите ПРОБЕЛ, чтобы начать/остановить запись.")

    while True:
        if is_recording:
            data = stream.read(FRAMES_PER_BUFFER)
            audio_frames.append(data)
        else:
            time.sleep(0.1)


def save_and_request_permission():
    """
    Сохраняет аудио, отправляет ИМЯ ФАЙЛА на сервер и ожидает разрешения (True)
    для следующей записи. БЛОКИРУЕТ программу, ожидая ответа.
    """
    global audio_frames, can_start_new_recording

    if not audio_frames:
        logger.warning("✗ Нет аудиоданных для отправки.")
        can_start_new_recording = True # Разрешаем новую попытку
        return

    frames_to_save = audio_frames[:]
    audio_frames.clear()

    # Убедимся, что директория для сохранения существует
    output_dir = os.path.dirname(WAVE_OUTPUT_FILENAME)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Создана директория: {output_dir}")

    logger.info("Сохранение аудио в файл...")
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(b''.join(frames_to_save))
    wf.close()
    logger.info(f"✓ Аудио сохранено в '{WAVE_OUTPUT_FILENAME}'.")

    # Получаем только имя файла из полного пути
    audio_filename = WAVE_OUTPUT_FILENAME[WAVE_OUTPUT_FILENAME.find('temp'):].replace("\\", "/")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            logger.info(f"Подключение к серверу {HOST}:{PORT}...")
            client_socket.connect((HOST, PORT))
            logger.info("✓ Подключено. Отправка имени файла...")

            # Отправляем имя файла в кодировке utf-8
            client_socket.sendall(audio_filename.encode('utf-8'))
            logger.info(f"✓ Имя файла '{audio_filename}' успешно отправлено.")

            # Ожидаем ответа от сервера
            logger.info("Ожидание ответа от сервера...")
            response = client_socket.recv(1024).decode('utf-8')

            logger.info("\n==========================================")
            logger.info(f"ОТВЕТ СЕРВЕРА: {response}")
            logger.info("==========================================\n")

            # Проверяем ответ сервера
            if response == 'True':
                logger.info("Начинаю воспроизводить аудио")
                play_audio()
                can_start_new_recording = True
                logger.info("✓ Сервер разрешил новую запись. Нажмите ПРОБЕЛ, чтобы начать.")
            else:
                logger.warning("✗ Сервер НЕ разрешил новую запись. Проверьте логи сервера.")
                # В этом случае `can_start_new_recording` останется False

    except ConnectionRefusedError:
        logger.error(f"✗ ОШИБКА: Не удалось подключиться к серверу по адресу {HOST}:{PORT}.")
        can_start_new_recording = True # Разрешаем новую попытку записи после ошибки
    except Exception as e:
        logger.error(f"✗ Произошла непредвиденная ошибка: {e}")
        can_start_new_recording = True # Разрешаем новую попытку записи после ошибки


def toggle_recording_state():
    """Переключает состояние записи и вызывает обработку."""
    global is_recording, can_start_new_recording

    if not is_recording:
        # Начинаем запись только если есть разрешение
        if can_start_new_recording:
            is_recording = True
            audio_frames.clear()
            logger.info("\n▶ Началась запись... (нажмите ПРОБЕЛ для остановки)")
        else:
            logger.warning("✗ Нельзя начать новую запись, пока сервер не обработает предыдущий запрос.")
    else:
        # Останавливаем запись
        is_recording = False
        can_start_new_recording = False  # Блокируем возможность новой записи до ответа сервера
        logger.info("\n⏹ Запись остановлена. Отправка запроса на сервер...")
        save_and_request_permission()


def play_audio():
    """
    Воспроизводит аудиофайл по указанному пути
    """
    audio_path = Path(WAVE_TO_PLAY)
    if not audio_path.exists():
        logger.error(f"Файл для воспроизведения не найден: {WAVE_TO_PLAY}")
        return
    try:
        audio_to_play = str(WAVE_TO_PLAY / f"output_{len(os.listdir(WAVE_TO_PLAY))-1}.wav")
        logger.info(f"Воспроизведение аудио: {audio_to_play}")
        playsound(str(audio_to_play))
        logger.info("Воспроизведение завершено.")
    except Exception as e:
        # Ловим возможные ошибки от библиотеки playsound
        logger.error(f"Не удалось воспроизвести аудиофайл. Ошибка: {e}")


def main():
    """Основная функция клиента."""
    global p, stream

    # Запускаем фоновый поток для записи с микрофона
    import threading
    recorder_thread = threading.Thread(target=audio_recorder, daemon=True)
    recorder_thread.start()

    keyboard.add_hotkey('space', toggle_recording_state)

    logger.info("Клиент запущен. Для выхода нажмите Ctrl+C.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nОстановка по команде пользователя.")
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        if p is not None:
            p.terminate()
        logger.info("Клиент завершил работу.")


if __name__ == '__main__':
    main()