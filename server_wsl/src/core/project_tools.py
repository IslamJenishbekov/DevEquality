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


def clone_project_from_github(project_gitname: str, project_path: str) -> bool:
    pass

