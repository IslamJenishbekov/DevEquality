"""
Project management tools for the voice-controlled assistant system.

This module provides comprehensive tools for creating and managing projects
in the voice-controlled assistant system. Projects are created in the
server_wsl/projects/ directory.
"""


import os
import git
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from .logger_config import logger


# Constants
PROJECTS_BASE_DIR = Path(__file__).resolve().parents[2] / "projects"
PROJECT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
MAX_PROJECT_NAME_LENGTH = 100
MIN_PROJECT_NAME_LENGTH = 1


def validate_project_name(project_name: str) -> None:
    """
    Validate a project name according to naming rules.

    Project names must:
    - Be between 1 and 100 characters long
    - Contain only alphanumeric characters, hyphens, and underscores
    - Not be empty or whitespace-only

    Args:
        project_name (str): The project name to validate.

    Raises:
        ValueError: If the project name is invalid, with a descriptive error message.
    """
    if not project_name or not project_name.strip():
        raise ValueError("Project name cannot be empty or contain only whitespace.")

    if len(project_name) < MIN_PROJECT_NAME_LENGTH:
        raise ValueError(
            f"Project name must be at least {MIN_PROJECT_NAME_LENGTH} character(s) long."
        )

    if len(project_name) > MAX_PROJECT_NAME_LENGTH:
        raise ValueError(
            f"Project name cannot exceed {MAX_PROJECT_NAME_LENGTH} characters. "
            f"Current length: {len(project_name)}."
        )

    if not PROJECT_NAME_PATTERN.match(project_name):
        raise ValueError(
            f"Project name '{project_name}' contains invalid characters. "
            f"Only alphanumeric characters, hyphens (-), and underscores (_) are allowed."
        )

    # Check for reserved names (common system names to avoid conflicts)
    reserved_names = {'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4',
                     'lpt1', 'lpt2', 'lpt3', '.', '..'}
    if project_name.lower() in reserved_names:
        raise ValueError(f"Project name '{project_name}' is a reserved system name.")

def create_project(
    project_name: str,
    base_dir: Optional[Path] = None,
    overwrite: bool = False
) -> Path:
    """
    Create a new project directory.

    This function creates a new empty project directory in the projects folder.

    Args:
        project_name (str): The name of the project to create.
                           Must contain only alphanumeric characters, hyphens, and underscores.
                           Length must be between 1 and 100 characters.
        base_dir (Optional[Path], optional): The base directory where the project should be created.
                                            Defaults to PROJECTS_BASE_DIR (server_wsl/projects/).
        overwrite (bool, optional): If True, overwrites existing project if it exists.
                                   If False, raises ValueError if project already exists.
                                   Defaults to False.

    Returns:
        Path: The absolute path to the created project directory.

    Raises:
        ValueError: If the project name is invalid, contains invalid characters,
                   is too long/short, or if the project already exists and overwrite=False.
        OSError: If there are permission issues, disk space problems, or other
                filesystem-related errors during project creation.
        Exception: For any other unexpected errors during project creation.

    Examples:
        >>> project_path = create_project("my_awesome_project")
        >>> print(project_path)
        /path/to/server_wsl/projects/my_awesome_project

        >>> # Create with description
        >>> project_path = create_project("data_analysis", description="ML data analysis project")

        >>> # Create with overwrite
        >>> project_path = create_project("existing_project", overwrite=True)

        >>> # Create in custom location
        >>> custom_dir = Path("/custom/location")
        >>> project_path = create_project("test_project", base_dir=custom_dir)
    """
    # Validate project name
    validate_project_name(project_name)

    # Determine base directory
    if base_dir is None:
        base_dir = PROJECTS_BASE_DIR

    # Ensure base directory exists
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured base directory exists: {base_dir}")
    except OSError as e:
        logger.error(f"Failed to create base directory {base_dir}: {e}")
        raise OSError(f"Failed to create base directory: {e}") from e

    # Create full project path
    project_path = base_dir / project_name

    # Check if project already exists
    if project_path.exists():
        if not overwrite:
            error_msg = (
                f"Project '{project_name}' already exists at {project_path}. "
                f"Use overwrite=True to replace it."
            )
            logger.warning(error_msg)
            raise ValueError(error_msg)
        else:
            logger.warning(
                f"Project '{project_name}' already exists. Overwriting due to overwrite=True."
            )
            try:
                # Remove existing project
                shutil.rmtree(project_path)
                logger.info(f"Removed existing project at {project_path}")
            except OSError as e:
                logger.error(f"Failed to remove existing project at {project_path}: {e}")
                raise OSError(f"Failed to remove existing project: {e}") from e

    # Create project directory
    try:
        project_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Successfully created project '{project_name}' at {project_path}")
    except OSError as e:
        logger.error(f"Failed to create project directory {project_path}: {e}")
        raise OSError(f"Failed to create project directory: {e}") from e

    return project_path

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

def delete_project(
    project_name: str,
    base_dir: Optional[Path] = None,
    force: bool = False
) -> bool:
    """
    Delete an existing project directory and all its contents.

    This function permanently removes a project directory and all its files.
    Use with caution as this operation cannot be undone.

    Args:
        project_name (str): The name of the project to delete.
                           Must be a valid project name format.
        base_dir (Optional[Path], optional): The base directory where the project is located.
                                            Defaults to PROJECTS_BASE_DIR (server_wsl/projects/).
        force (bool, optional): If True, suppresses the project existence check and attempts
                               deletion regardless. If False, raises ValueError if project
                               doesn't exist. Defaults to False.

    Returns:
        bool: True if the project was successfully deleted, False if the project
              didn't exist and force=True.

    Raises:
        ValueError: If the project name is invalid, or if the project doesn't exist
                   and force=False.
        OSError: If there are permission issues, files are locked, or other
                filesystem-related errors during deletion.
        Exception: For any other unexpected errors during project deletion.

    Examples:
        >>> success = delete_project("old_project")
        >>> print(success)
        True

        >>> # Force delete (no error if doesn't exist)
        >>> success = delete_project("maybe_exists", force=True)

        >>> # Delete from custom location
        >>> custom_dir = Path("/custom/location")
        >>> success = delete_project("test_project", base_dir=custom_dir)
    """
    # Validate project name
    validate_project_name(project_name)

    # Determine base directory
    if base_dir is None:
        base_dir = PROJECTS_BASE_DIR

    # Create full project path
    project_path = base_dir / project_name

    # Check if project exists
    if not project_path.exists():
        if not force:
            error_msg = f"Project '{project_name}' does not exist at {project_path}."
            logger.warning(error_msg)
            raise ValueError(error_msg)
        else:
            logger.info(
                f"Project '{project_name}' does not exist at {project_path}. "
                f"No deletion needed (force=True)."
            )
            return False

    # Verify it's a directory
    if not project_path.is_dir():
        error_msg = (
            f"Path {project_path} exists but is not a directory. "
            f"Cannot delete as a project."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Perform deletion
    try:
        shutil.rmtree(project_path)
        logger.info(f"Successfully deleted project '{project_name}' at {project_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to delete project at {project_path}: {e}")
        raise OSError(
            f"Failed to delete project '{project_name}': {e}. "
            f"This may be due to permission issues or files being in use."
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error while deleting project {project_path}: {e}")
        raise


def list_projects(base_dir: Optional[Path] = None) -> list[str]:
    """
    List all projects in the projects directory.

    Returns a list of project names (directory names) found in the base directory.
    Only returns actual directories, not files.

    Args:
        base_dir (Optional[Path], optional): The base directory to list projects from.
                                            Defaults to PROJECTS_BASE_DIR (server_wsl/projects/).

    Returns:
        list[str]: A sorted list of project names. Returns an empty list if no projects
                   exist or if the base directory doesn't exist.

    Raises:
        OSError: If there are permission issues reading the directory.
        Exception: For any other unexpected errors during directory listing.

    Examples:
        >>> projects = list_projects()
        >>> print(projects)
        ['project1', 'project2', 'my_awesome_project']

        >>> # List from custom location
        >>> custom_dir = Path("/custom/location")
        >>> projects = list_projects(base_dir=custom_dir)
    """
    # Determine base directory
    if base_dir is None:
        base_dir = PROJECTS_BASE_DIR

    # Check if base directory exists
    if not base_dir.exists():
        logger.warning(f"Base directory {base_dir} does not exist. Returning empty list.")
        return []

    try:
        # Get all directories in base_dir
        projects = [
            item.name for item in base_dir.iterdir()
            if item.is_dir() and not item.name.startswith('.')
        ]
        projects.sort()
        logger.debug(f"Found {len(projects)} project(s) in {base_dir}")
        return projects
    except OSError as e:
        logger.error(f"Failed to list projects in {base_dir}: {e}")
        raise OSError(f"Failed to list projects: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error while listing projects: {e}")
        raise


def project_exists(
    project_name: str,
    base_dir: Optional[Path] = None
) -> bool:
    """
    Check if a project exists.

    Args:
        project_name (str): The name of the project to check.
        base_dir (Optional[Path], optional): The base directory where to check for the project.
                                            Defaults to PROJECTS_BASE_DIR (server_wsl/projects/).

    Returns:
        bool: True if the project exists and is a directory, False otherwise.

    Raises:
        ValueError: If the project name is invalid.

    Examples:
        >>> exists = project_exists("my_project")
        >>> if exists:
        ...     print("Project exists!")
    """
    # Validate project name
    validate_project_name(project_name)

    # Determine base directory
    if base_dir is None:
        base_dir = PROJECTS_BASE_DIR

    # Create full project path
    project_path = base_dir / project_name

    # Check existence and ensure it's a directory
    exists = project_path.exists() and project_path.is_dir()
    logger.debug(f"Project '{project_name}' exists: {exists}")

    return exists


def get_project_path(
    project_name: str,
    base_dir: Optional[Path] = None
) -> Path:
    """
    Get the absolute path to a project directory.

    Args:
        project_name (str): The name of the project.
        base_dir (Optional[Path], optional): The base directory where the project is located.
                                            Defaults to PROJECTS_BASE_DIR (server_wsl/projects/).

    Returns:
        Path: The absolute path to the project directory.

    Raises:
        ValueError: If the project name is invalid or if the project doesn't exist.

    Examples:
        >>> path = get_project_path("my_project")
        >>> print(path)
        /path/to/server_wsl/projects/my_project
    """
    # Validate project name
    validate_project_name(project_name)

    # Determine base directory
    if base_dir is None:
        base_dir = PROJECTS_BASE_DIR

    # Create full project path
    project_path = base_dir / project_name

    # Verify project exists
    if not project_path.exists() or not project_path.is_dir():
        raise ValueError(
            f"Project '{project_name}' does not exist at {project_path}."
        )

    return project_path.resolve()
