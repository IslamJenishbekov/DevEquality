from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
import operator
import os
import json
from ..core.logger_config import logger


class AgentState(TypedDict):
    """
    Определяет структуру состояния для графа голосового ассистента.

    Это состояние отслеживает как историю диалога для LLM, так и текущий
    контекст работы ассистента (файлы, аудио, текст для озвучки).
    """

    # --- Диалоговая часть ---

    # `messages` будет накапливать историю сообщений.
    # Annotated[..., operator.add] говорит графу "не заменяй, а добавляй".
    # Каждый раз, когда узел вернет ключ "messages", новый список сообщений
    # будет добавлен к старому.
    messages: Annotated[List[BaseMessage], operator.add]

    # --- Входные данные от пользователя ---

    # Путь к последнему записанному аудиофайлу.
    # Это значение будет перезаписываться при каждой новой записи.
    audio_filepath: str

    # Расшифрованный текст из последнего аудиофайла.
    # Также перезаписывается.
    transcribed_message: str

    # --- Контекст работы ассистента ---

    # Текущий проект или рабочая область.
    curr_project: str

    # Текущая директория, в которой работает ассистент.
    curr_dir: str

    # Текущий файл, с которым работает ассистент.
    curr_file: str

    # --- Выходные данные для пользователя ---

    # Текст, который ассистент должен произнести.
    # Генерируется LLM или другим инструментом.
    text_to_pronounce: str

    # Путь к сгенерированному аудиофайлу, который нужно воспроизвести.
    pronounced_audio: str


def get_default_state() -> AgentState:
    """
    Фабричная функция для создания и возврата состояния по умолчанию.
    Гарантирует консистентность структуры состояния во всем приложении.
    """
    return {
        "messages": [],
        "transcribed_message": "",
        "audio_filepath": "",
        "curr_project": None,
        "curr_dir": None,
        "curr_file": None,
        "text_to_pronounce": "",
        "pronounced_audio": ""
    }


def load_state(state_path: str) -> AgentState:
    if os.path.exists(state_path):
        logger.info(f"Загрузка состояния из {state_path}")
        with open(state_path, 'r') as f:
            return json.load(f)
    logger.info("Файл состояния не найден. Используется состояние по умолчанию.")
    return get_default_state()


def save_state(state: dict, state_path: str) -> None:
    logger.info(f"Сохранение нового состояния в {state_path}")
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=4)
