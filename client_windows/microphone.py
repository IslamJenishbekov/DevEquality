import sys
from pathlib import Path
script_path = Path(__file__).resolve()
project_root = script_path.parents[1]
sys.path.insert(0, str(project_root))
from server_wsl.src.core.logger_config import logger
import os
import pyaudio
import wave
import shutil
import socket
import time
import keyboard
from configparser import ConfigParser
from playsound import playsound
import sounddevice as sd
import soundfile as sf
import numpy as np

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
                logger.info("Сервер обработал запрос. Начинаю воспроизводить аудио ответа...")

                try:
                    # Находим самый свежий файл "output_*.wav" в папке для ответов
                    response_dir = Path(WAVE_TO_PLAY)
                    # Получаем список всех файлов ответа и сортируем, чтобы последний был действительно последним
                    response_files = sorted(response_dir.glob("output_*.wav"))

                    if response_files:
                        latest_response_file = response_files[-1]
                        play_audio_on_device_soundfile(str(latest_response_file), 6)  # <-- ПЕРЕДАЁМ КОНКРЕТНЫЙ ФАЙЛ
                    else:
                        logger.warning(f"✗ Не найден файл ответа для воспроизведения в папке {WAVE_TO_PLAY}")
                except Exception as e:
                    logger.error(f"Ошибка при поиске или воспроизведении файла ответа: {e}")

                can_start_new_recording = True
                logger.info("✓ Сервер разрешил новую запись. Можно продолжать.")
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


def play_audio(file_path_to_play: str = str(Path(WAVE_TO_PLAY))):
    """
    Воспроизводит аудиофайл по указанному пути.

    :param file_path_to_play: Полный путь к аудиофайлу для воспроизведения.
    """
    audio_path = Path(file_path_to_play)
    if not audio_path.exists() or not audio_path.is_file():
        logger.error(f"✗ Файл для воспроизведения не найден или не является файлом: {file_path_to_play}")
        return

    try:
        logger.info(f"▶ Воспроизведение аудио: {file_path_to_play}")
        playsound(str(audio_path))
        logger.info("✓ Воспроизведение завершено.")
    except Exception as e:
        # Ловим возможные ошибки от библиотеки playsound
        logger.error(f"Не удалось воспроизвести аудиофайл '{file_path_to_play}'. Ошибка: {e}")

def main():
    """Основная функция клиента."""
    global p, stream

    # Запускаем фоновый поток для записи с микрофона
    import threading
    delete_trash_before_scenarios()
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


def run_scenario_with_audio_playing(scenario_folder_path: str):
    """
    Автоматически отправляет все .wav файлы из указанной папки на сервер.

    Для каждого файла:
    1. Воспроизводит аудио ЗАПРОСА.
    2. Загружает аудиоданные из файла.
    3. Имитирует завершение записи.
    4. Вызывает save_and_request_permission для отправки и получения ответа.
    5. Функция save_and_request_permission воспроизводит аудио ОТВЕТА.
    6. Ожидает завершения, прежде чем перейти к следующему файлу.

    :param scenario_folder_path: Путь к папке с аудиофайлами для сценария.
    """
    global audio_frames, p, can_start_new_recording

    # Проверяем, существует ли папка
    if not os.path.isdir(scenario_folder_path):
        logger.error(f"✗ Папка для сценария не найдена: {scenario_folder_path}")
        return

    # Получаем отсортированный список .wav файлов, чтобы порядок был предсказуем
    audio_files = sorted([f for f in os.listdir(scenario_folder_path) if f.endswith('.wav')])

    if not audio_files:
        logger.warning(f"✗ В папке '{scenario_folder_path}' не найдено .wav файлов.")
        return

    logger.info(f"▶▶▶ НАЧАЛО СЦЕНАРИЯ. Найдено файлов: {len(audio_files)} ▶▶▶")

    for filename in audio_files:
        # Убедимся, что можем начать "запись"
        if not can_start_new_recording:
            logger.warning("Ожидание разрешения от сервера перед отправкой следующего файла...")
            while not can_start_new_recording:
                time.sleep(0.5)

        full_path = os.path.join(scenario_folder_path, filename)
        logger.info(f"\n{'='*15} Обработка файла: {filename} {'='*15}")

        try:
            # --- НОВЫЙ ШАГ: ВОСПРОИЗВОДИМ АУДИО ЗАПРОСА ---
            logger.info("--- ШАГ 1: Воспроизведение ЗАПРОСА ---")
            play_audio_on_device_soundfile(full_path, 6)
            # --------------------------------------------------

            logger.info("--- ШАГ 2: Отправка на сервер ---")
            # Читаем данные из файла сценария
            with wave.open(full_path, 'rb') as wf:
                # if (wf.getnchannels() != CHANNELS or
                #         wf.getsampwidth() != p.get_sample_size(FORMAT) or
                #         wf.getframerate() != SAMPLE_RATE):
                #     logger.error(f"✗ Файл {filename} имеет несовместимый аудиоформат. Пропускаем.")
                #     continue
                audio_data = wf.readframes(wf.getnframes())

            # Имитируем, что эти данные были только что записаны
            audio_frames.clear()
            audio_frames.append(audio_data)

            # Блокируем новые "записи" и отправляем данные на сервер
            can_start_new_recording = False
            save_and_request_permission()
            # Теперь save_and_request_permission сама вызовет play_audio для ответа
            # и установит can_start_new_recording = True

            # Небольшая пауза между файлами для наглядности
            time.sleep(3)

        except Exception as e:
            logger.error(f"✗ Ошибка при обработке файла {filename}: {e}")
            # В случае ошибки разрешаем попытку для следующего файла
            can_start_new_recording = True

    logger.info(f"\n✅✅✅ СЦЕНАРИЙ УСПЕШНО ЗАВЕРШЕН ✅✅✅")


def scenario_main():
    global p
    delete_trash_before_scenarios()
    SCENARIO_FOLDER = str(Path(__file__).resolve().parents[1] / "server_wsl" / "temp_audio" / "scenarios" / "scenario5")

    # Инициализируем PyAudio, т.к. save_and_request_permission зависит от него
    p = pyaudio.PyAudio()
    try:
        # Запускаем сценарий
        run_scenario_with_audio_playing(SCENARIO_FOLDER)
    except Exception as e:
        logger.error(f"Произошла критическая ошибка во время выполнения сценария: {e}")
    finally:
        # Освобождаем ресурсы PyAudio
        p.terminate()
        logger.info("Клиент завершил работу.")


def delete_trash_before_scenarios():
    """
    Очищает временные файлы и файлы состояния перед запуском сценария.
    """
    logger.info("--- Запуск очистки перед сценарием ---")
    pronounced_folder = Path(__file__).resolve().parents[1] / "server_wsl" / "temp_audio" / "pronounced"
    received_folder = Path(__file__).resolve().parents[1] / "server_wsl" / "temp_audio" / "received"
    state_json_path = Path(__file__).resolve().parents[1] / "server_wsl" / "state" / "state.json"
    projects_path = Path(__file__).resolve().parents[1] / "server_wsl" / "projects"

    for folder in [pronounced_folder, received_folder]:
        if not folder.is_dir():
            logger.warning(f"Папка для очистки не найдена, пропускаем: {folder}")
            continue
        try:
            files_to_delete = list(folder.glob("*.wav"))
            if not files_to_delete:
                logger.info(f"Папка {folder} уже чиста от .wav файлов.")
                continue
            for wav_file in files_to_delete:
                wav_file.unlink()
            logger.info(f"✓ Удалено {len(files_to_delete)} .wav файлов из {folder}")
        except Exception as e:
            logger.error(f"✗ Ошибка при очистке папки {folder}: {e}")

    if state_json_path.is_file():
        try:
            state_json_path.unlink()
            logger.info(f"✓ Файл состояния {state_json_path} успешно удален.")
        except Exception as e:
            logger.error(f"✗ Не удалось удалить файл состояния {state_json_path}: {e}")
    else:
        logger.info("Файл state.json не найден, очистка не требуется.")
    if projects_path.is_dir():
        logger.info(f"Начинаю очистку папки проектов: {projects_path}")
        try:
            # Получаем список всех элементов в папке, которые являются директориями
            subdirectories = [item for item in projects_path.iterdir() if item.is_dir()]

            if not subdirectories:
                logger.info(f"Папка {projects_path} не содержит подпапок для удаления.")
            else:
                for project_dir in subdirectories:
                    shutil.rmtree(project_dir)  # Рекурсивно удаляем папку и всё её содержимое
                    logger.info(f"✓ Удалена папка проекта: {project_dir.name}")
                logger.info(f"✓ Успешно удалено {len(subdirectories)} папок из {projects_path}")

        except Exception as e:
            logger.error(f"✗ Ошибка при очистке папки проектов {projects_path}: {e}")
    else:
        logger.warning(f"Папка проектов не найдена, пропускаем очистку: {projects_path}")
    logger.info("--- Очистка завершена ---")


def play_audio_on_device_soundfile(file_path: str, device_id: int = None, volume: float = 1.0):
    """
    Воспроизводит аудиофайл с заданной громкостью на указанном устройстве.

    :param file_path: Полный путь к аудиофайлу.
    :param device_id: ID устройства для воспроизведения. Если None, используется устройство по умолчанию.
    :param volume: Уровень громкости от 0.0 до 1.0 (и выше, но возможны искажения).
    """
    try:
        # Читаем аудиофайл в виде массива NumPy
        data, fs = sf.read(file_path, dtype='float32')

        # Регулируем громкость
        # Умножаем каждый семпл в аудиоданных на коэффициент громкости
        adjusted_data = data * volume

        # Ограничиваем значения, чтобы избежать "клиппинга" (искажений)
        # Все значения выше 1.0 будут установлены на 1.0, а ниже -1.0 - на -1.0
        np.clip(adjusted_data, -1.0, 1.0, out=adjusted_data)

        # Устанавливаем устройство вывода, если оно указано
        if device_id is not None:
            sd.default.device = device_id

        device_info = f"устройстве ID: {device_id}" if device_id is not None else "устройстве по умолчанию"
        logger.info(f"▶️  Воспроизведение '{file_path}' на {device_info} с громкостью {int(volume * 100)}%")

        # Воспроизводим измененные аудиоданные
        sd.play(adjusted_data, fs)

        # Ожидаем завершения воспроизведения
        sd.wait()

        logger.info("✅ Воспроизведение завершено.")

    except FileNotFoundError:
        logger.error(f"✗ Файл для воспроизведения не найден: {file_path}")
    except Exception as e:
        logger.error(f"Не удалось воспроизвести аудиофайл '{file_path}'. Ошибка: {e}")


if __name__ == '__main__':
    #main()
    scenario_main()