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

    logger.info(f"Результат транскрибации: '{transcribed_message}'")

    return {
        "transcribed_message": transcribed_message,
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
        return {"text_to_pronounce": "We couldn't define the name of the project."}
    project_path = os.path.join(USER_WORKSPACE, project_name)
    if os.path.exists(project_path):
        return {"text_to_pronounce": f"Project {project_name} already exists."}
    created = project_tools.create_project(project_path)
    if not created:
        return {"text_to_pronounce": f"Project {project_name} wasn't created."}
    return {"text_to_pronounce": f"Project {project_name} successfully created."}


def git_clone_project_node(state: AgentState) -> Dict:
    """

    """
    pass


def create_directory_node(state: AgentState) -> Dict:
    """

    """
    directory_name = state.get("curr_dir")
    project_name = state.get("curr_project")
    if not project_name:
        return {"text_to_pronounce": "We couldn't define the project"}
    if not directory_name:
        return {"text_to_pronounce": "We couldn't define the name of the directory."}
    dir_path = f"{USER_WORKSPACE}/{project_name}/{directory_name}"
    if os.path.exists(dir_path):
        return {"text_to_pronounce": f"Directory {directory_name} already exists."}

    created = dir_tools.create_directory(dir_path)
    if not created:
        return {"text_to_pronounce": f"Directory {directory_name} wasn't created."}
    return {"text_to_pronounce": "Directory {directory_name} successfully created."}


def create_file_node(state: AgentState) -> Dict:
    """

    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get(
        "curr_dir"), state.get("curr_file")
    if not curr_project:
        return {"text_to_pronounce": "We couldn't define the project"}
    if not curr_dir:
        return {"text_to_pronounce": "We couldn't define the directory"}
    if not curr_file:
        return {"text_to_pronounce": "We couldn't define the file"}
    filepath = f"{curr_project}/{curr_dir}/{curr_file}"
    if os.path.exists(filepath):
        return {"text_to_pronounce": f"File {curr_file} already exists."}
    created = file_tools.create_file(filepath)
    if not created:
        return {"text_to_pronounce": f"File {filepath} wasn't created."}
    return {"text_to_pronounce": f"File {filepath} successfully created."}


def edit_file_node(state: AgentState) -> Dict:
    """

    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    if not curr_project:
        return {"text_to_pronounce": "We couldn't define the project"}
    if not curr_dir:
        return {"text_to_pronounce": "We couldn't define the directory"}
    if not curr_file:
        return {"text_to_pronounce": "We couldn't define the file"}
    filepath = f"{curr_project}/{curr_dir}/{curr_file}"
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} does not exist."}
    edited = file_tools.edit_file(filepath)
    if not edited:
        return {"text_to_pronounce": f"Something went wrong editing {filepath}."}
    return {"text_to_pronounce": f"File {filepath} successfully edited."}


def run_file_node(state: AgentState) -> Dict:
    """

    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    if not curr_project:
        return {"text_to_pronounce": "We couldn't define the project"}
    if not curr_dir:
        return {"text_to_pronounce": "We couldn't define the directory"}
    if not curr_file:
        return {"text_to_pronounce": "We couldn't define the file"}
    filepath = f"{curr_project}/{curr_dir}/{curr_file}"
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} doesn't exist."}
    result = file_tools.run_file(filepath)
    if result:
        return {"text_to_pronounce": f"File was ran, and output is: {result}."}
    return {"text_to_pronounce": "Some troubles happened!"}



def get_file_content_node(state: AgentState) -> Dict:
    """

    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    if not curr_project:
        return {"text_to_pronounce": "We couldn't define the project"}
    if not curr_dir:
        return {"text_to_pronounce": "We couldn't define the directory"}
    if not curr_file:
        return {"text_to_pronounce": "We couldn't define the file"}
    filepath = f"{curr_project}/{curr_dir}/{curr_file}"
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} doesn't exist."}
    content = file_tools.read_file(filepath)
    if content == "not empty, but error":
        return {"text_to_pronounce": "Some troubles happened!"}
    if content == "":
        return {"text_to_pronounce": f"File {filepath} is empty"}
    return {"text_to_pronounce": f"System read file and content is: {content}"}



def summarize_file_content_node(state: AgentState) -> Dict:
    """

    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    if not curr_project:
        return {"text_to_pronounce": "We couldn't define the project"}
    if not curr_dir:
        return {"text_to_pronounce": "We couldn't define the directory"}
    if not curr_file:
        return {"text_to_pronounce": "We couldn't define the file"}
    filepath = f"{curr_project}/{curr_dir}/{curr_file}"
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} doesn't exist."}
    summary = file_tools.summarize_file(filepath, llm_service)
    if not summary:
        return {"text_to_pronounce": "Some troubles happened!"}
    return {"text_to_pronounce": summary}


def unknown_operation_node(state: AgentState) -> Dict:
    """

    """
    return {"text_to_pronounce": "We couldn't understand your operation, maybe it hasn't implemented yet"}