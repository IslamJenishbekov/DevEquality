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


def edit_file(file_path: str, transcribed_message: str, llm) -> str:
    try:
        with open(file_path, 'w') as f:
            existing_code = f.read()
        response = llm.edit_file(existing_code, transcribed_message)
        return response
    except Exception as e:
        logger.error(e)
        return ""


def run_file(file_path: str) -> str:
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True)
        answer = f"Your code output: {result.stdout}"
        if result.stderr:
            answer += f"\nBut then this error occurred: {result.stderr}"
        return answer
    except Exception as e:
        logger.error(e)
        return ""


def summarize_file(file_path: str, llm_service: GeminiService):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        response = llm_service.summarize_file_content(content)
        return response
    except Exception as e:
        logger.error(e)
        return ""
