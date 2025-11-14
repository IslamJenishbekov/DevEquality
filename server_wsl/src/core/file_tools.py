import os
import subprocess
from ..core.logger_config import logger
from ..services.llm_service import GeminiService


def create_file(file_path: str) -> bool:
    try:
        with open(file_path, 'w') as f:
            f.write("")
        return True
    except Exception as e:
        logger.error(e)
        return False


def read_file(file_path: str) -> str:
    try:
        with open(file_path, 'r') as f:
            data = f.read()
        return data
    except Exception as e:
        logger.error(e)
        return "not empty, but error"


def edit_file(file_path: str, new_content: str) -> bool:
    try:
        with open(file_path, 'w') as f:
            f.write(new_content)
        return True
    except Exception as e:
        logger.error(e)
        return False


def run_file(file_path: str) -> str:
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True)
        answer = f"{result.stdout}"
        if result.stderr:
            answer += f"\nBut then this error occurred: {result.stderr}"
        return answer
    except Exception as e:
        logger.error(e)
        return ""

