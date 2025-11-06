import socket
from src.core.logger_config import logger
from configparser import ConfigParser
from pathlib import Path


# --- Конфигурация ---
config_file = str(Path(__file__).resolve().parents[1] / "client_windows" / 'config.ini')
config = ConfigParser()
config.read(config_file)

# --- Сетевые настройки ---
HOST = config['SERVER']['host']
PORT = int(config['SERVER']['port'])


def main():
    """
    Временная заглушка.
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

                    response = 'Тут должна быть вызвана функция логика лангграфа'
                    input("Ждет моего сигнала")
                    conn.sendall(response.encode('utf-8'))

                    logger.info(f"Отправлен ответ '{response}' клиенту {addr}")

                except ConnectionResetError:
                    logger.warning(f"Соединение с {addr} было сброшено клиентом.")
                except Exception as e:
                    logger.error(f"Произошла ошибка при обработке клиента {addr}: {e}")


if __name__ == '__main__':
    main()