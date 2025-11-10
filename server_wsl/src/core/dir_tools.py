import os
from ..core.logger_config import logger

def create_directory(directory_path: str) -> bool:
    try:
        os.makedirs(directory_path)
        return True
    except Exception as e:
        logger.error(e)
        return False