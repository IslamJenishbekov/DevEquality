import os
from typing import Dict
from .state import AgentState
from ..services.asr_service import TranscriptionService
from ..services.tts_service import TextToSpeechService
from ..services.llm_service import GeminiService
from ..core.logger_config import logger
from ..core import file_tools, dir_tools, project_tools


logger.info("Загружаем ASR модель")
asr_service = TranscriptionService()
logger.info("Экземпляр TranscriptionService создан.")

logger.info("Загружаем TTS модель")
tts_service = TextToSpeechService()
logger.info("Экземпляр TextToSpeechService создан.")

logger.info("Подключаем LLM модель")
llm_service = GeminiService()
logger.info("Экземпляр Gemini успешно создан")

USER_WORKSPACE = r"projects/"

def transcribe_audio_node(state: AgentState) -> Dict:
    """
    Узел графа, который отвечает за транскрибацию аудио в текст.

    Args:
        state (AgentState): Текущее состояние графа.
                           Ожидается, что поле 'audio_filepath' уже заполнено.

    Returns:
        Dict: Словарь с обновлением для состояния.
              В данном случае, обновляется поле 'transcribed_message'.
    """
    audio_path = state.get("audio_filepath")
    if not audio_path:
        raise ValueError("No audio_filepath in state['audio_filepath']. Transcribation impossible")
    elif not os.path.exists(audio_path):
        raise ValueError(f"{audio_path} - system couldn't find this file. Transcribation impossible")

    transcribed_message = asr_service.transcribe(audio_path)
    # Добавляем новую информацию в историю сообщений для LLM
    # Это хорошая практика, чтобы LLM видел всю историю взаимодействия
    messages = state.get("messages", [])
    messages.append({
        "audio_filepath": audio_path,
        "transcribed_message": transcribed_message
    })

    logger.info(f"Результат транскрибации: '{transcribed_message}'")

    return {
        "transcribed_message": transcribed_message,
        "messages": messages
    }


def synthesize_audio_node(state: AgentState) -> Dict:
    """
    Узел графа, который отвечает за перевод конечного ответа в аудио и его сохранение.

    Args:
        state (AgentState): Текущее состояние графа.
                           Ожидается, что поле 'text_to_pronounce' уже заполнено.

    Returns:
        Dict: Словарь с обновлением для состояния.
              В данном случае, обновляется поле 'pronounced_audio'.
    """
    target_filename = r"temp_audio/pronounced/output.wav"
    text_to_pronounce = state.get("text_to_pronounce")
    if not text_to_pronounce:
        text_to_pronounce = "It is just a demo"
    tts_service.synthesize(text_to_pronounce, target_filename)
    messages = state.get("messages", [])
    messages.append({
        "text_to_pronounce": text_to_pronounce,
        "pronounced_audio": target_filename,
    })

    return {
        "pronounced_audio": target_filename,
    }


def get_operation_and_object_name_node(state: AgentState) -> Dict:
    """Определяет намерение пользователя и извлекает связанные данные с помощью LLM.

    Этот узел является "мозговым центром" графа. Он берет транскрибированный
    текст из состояния, отправляет его в языковую модель (LLM) для анализа
    и получает структурированный ответ. Затем он обновляет состояние графа,
    добавляя в него определенную операцию (например, "create_file") и имя
    объекта (например, "main.py"), над которым нужно выполнить эту операцию.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поле
                            `transcribed_message` уже заполнено.

    Returns:
        Dict: Словарь с обновлениями для состояния графа. Обязательно
              содержит ключ `operation` для дальнейшей маршрутизации, а также
              может содержать ключи `curr_file`, `curr_dir` или `curr_project`
              с извлеченным именем объекта.

    Raises:
        ValueError: Если в состоянии отсутствует `transcribed_message`.
    """

    transcribed_message = state.get("transcribed_message")
    if not transcribed_message:
        raise ValueError("No transcribed_message in state['transcribed_message']")
    llm_answer = llm_service.choose_operation(transcribed_message)
    logger.info(f"Ответ модели: {llm_answer}")
    state_to_return = {"operation": llm_answer['operation']}
    if "file" in llm_answer['operation']:
        state_to_return["curr_file"] = llm_answer['object_name']
    elif "directory" in llm_answer['operation']:
        state_to_return["curr_dir"] = llm_answer['object_name']
    elif "project" in llm_answer['operation']:
        state_to_return["curr_project"] = llm_answer['object_name']
    return state_to_return


def choose_operation_node(state: AgentState) -> str:
    """Принимает решение о маршрутизации графа на основе операции.

    Эта функция используется в качестве "диспетчера" (conditional edge)
    в графе. Она не выполняет никакой работы и не изменяет состояние.
    Ее единственная задача — прочитать поле `operation` из текущего
    состояния и вернуть его значение в виде строки. Эта строка затем
    используется графом для выбора следующего узла для выполнения.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поле
                            `operation` было заполнено предыдущим узлом
                            (например, `get_operation_and_object_name_node`).

    Returns:
        str: Строка с названием операции (например, "create_file", "run_file",
             "unknown"), которая будет использована как ключ для маршрутизации.
    """
    operation = state.get("operation")
    logger.info(f"Операция выбрана: {operation}")
    return operation


def create_project_node(state: AgentState) -> Dict:
    """

    """
    project_name = state.get("curr_project")
    if not project_name:
        raise ValueError("No project_name in state['curr_project']")
    project_path = os.path.join(USER_WORKSPACE, project_name)
    if os.path.exists(project_path):
        return {"text_to_pronounce": f"Project {project_name} already exists."}
    created = project_tools.create_project(project_path)
    if not created:
        return {"text_to_pronounce": f"Project {project_name} wasn't created."}
    return {"text_to_pronounce": f"Project {project_name} successfully created."}


def git_clone_project_node(state: AgentState) -> Dict:
    pass


def create_directory_node(state: AgentState) -> Dict:
    pass


def create_file_node(state: AgentState) -> Dict:
    pass


def edit_file_node(state: AgentState) -> Dict:
    pass


def run_file_node(state: AgentState) -> Dict:
    pass


def get_file_content_node(state: AgentState) -> Dict:
    pass


def summarize_file_content_node(state: AgentState) -> Dict:
    pass

def unknown_operation_node(state: AgentState) -> Dict:
    pass