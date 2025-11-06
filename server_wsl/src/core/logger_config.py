import logging
import os
from datetime import datetime

# Папка для логов
LOG_DIR = os.path.join(os.path.dirname(__file__), "../../logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Имя файла по дате
log_filename = os.path.join(LOG_DIR, f"{datetime.now():%Y-%m-%d}.log")

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("DevEquality")
