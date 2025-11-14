import socket
from src.core.logger_config import logger
from configparser import ConfigParser
from pathlib import Path
from src.graph.state import load_state, save_state
from src.graph.workflow import app
import os
import shutil


# --- Конфигурация ---
config_file = str(Path(__file__).resolve().parents[1] / "client_windows" / 'config.ini')
config = ConfigParser()
config.read(config_file)

# --- Сетевые настройки ---
HOST = config['SERVER']['host']
PORT = int(config['SERVER']['port'])

# --- КОНСТАНТЫ ---
STATE_PATH = r'state/state.json'


def main():
    """
    Основной main
    """
    # Создаем TCP/IP сокет
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        # Привязываем сокет к адресу и порту
        server_socket.bind((HOST, PORT))

        # Начинаем прослушивать входящие подключения
        server_socket.listen()

        logger.info(f"Сервер запущен и слушает на {HOST}:{PORT}")

        while True:
            logger.info("Ожидание нового подключения...")

            # Принимаем подключение
            # conn - это новый сокет для обмена данными с клиентом
            # addr - это адрес клиента
            conn, addr = server_socket.accept()

            # Используем `with` для автоматического закрытия сокета `conn`
            with conn:
                logger.info(f"Установлено соединение с {addr}")

                try:
                    # Получаем данные от клиента. 1024 байта должно быть достаточно для имени файла.
                    # .decode('utf-8') преобразует байты в строку.
                    received_data = conn.recv(1024).decode('utf-8')

                    if not received_data:
                        logger.warning(f"Клиент {addr} отключился, не отправив данных.")
                        continue  # Переходим к следующей итерации цикла, ожидая нового клиента

                    logger.info(f"Получено сообщение (имя файла): '{received_data}'")
                    response = main_imitation(received_data)
                    conn.sendall(response.encode('utf-8'))

                    logger.info(f"Отправлен ответ '{response}' клиенту {addr}")

                except ConnectionResetError:
                    logger.warning(f"Соединение с {addr} было сброшено клиентом.")
                except Exception as e:
                    logger.error(f"Произошла ошибка при обработке клиента {addr}: {e}")


# may be used without client
def main_imitation(audio_path: str = "temp_audio/received/create_project.wav"):
    """
    Временная заглушка
    """
    audio_path = Path(audio_path)
    current_state = load_state(STATE_PATH)
    try:
        initial_graph_input = {
            **current_state,
            "audio_filepath": str(audio_path),
        }
        logger.info("Запуск графа")
        final_state = app.invoke(initial_graph_input)
        logger.info("Граф завершил работу")
        save_state(final_state, STATE_PATH)
    except Exception as e:
        logger.error(f"Ошибка во время выполнения графа: {e}")
    return "True"


def run_scenario(scenario_num: str):
    output_dir = 'temp_audio/pronounced/'
    for file in os.listdir(output_dir):
        if file.endswith(".wav"):
            os.remove(os.path.join(output_dir, file))
    state_file = "state/state.json"
    if os.path.exists(state_file):
        os.remove(state_file)
    parent_folder = "projects"
    for item in os.listdir(parent_folder):
        item_path = os.path.join(parent_folder, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
    scenario_path = f"temp_audio/scenarios/scenario{scenario_num}/"
    for audio in Path(scenario_path).rglob("*.wav"):
        main_imitation(str(audio))
        input()

if __name__ == '__main__':
    #main_imitation('temp_audio/scenarios/scenario1/3.wav')
    main()
    #run_scenario("3")