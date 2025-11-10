import os
import git
from ..core.logger_config import logger

def create_project(project_path: str) -> bool:
    try:
        os.makedirs(project_path)
        return True
    except Exception as e:
        logger.error(f"Fail: {e}")
        return False


def clone_project_from_github(git_repo_url: str, project_path: str) -> bool:
    try:
        # Основная команда клонирования с отслеживанием прогресса
        git.Repo.clone_from(
            git_repo_url,
            project_path,
        )
        logger.info(f"Репозиторий '{git_repo_url}' успешно склонирован в '{project_path}'.")
        return True

    except git.exc.GitCommandError as e:
        # Обработка наиболее частых ошибок Git
        if "Authentication failed" in str(e):
            logger.error(
                f"Ошибка аутентификации при клонировании '{git_repo_url}'. Возможно, это приватный репозиторий.")
        elif "not found" in str(e):
            logger.error(f"Репозиторий по URL '{git_repo_url}' не найден. Проверьте правильность ссылки.")
        else:
            logger.error(f"Произошла ошибка Git при клонировании. Status: {e.status}, Stderr: {e.stderr}")
        return False

    except Exception as e:
        # Обработка других возможных ошибок (например, проблемы с сетью)
        logger.error(f"Произошла непредвиденная ошибка при клонировании '{git_repo_url}': {e}")
        return False

