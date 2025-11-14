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
    number_files = len(os.listdir("temp_audio/pronounced/"))
    target_filename = f"temp_audio/pronounced/output_{number_files}.wav"
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
        curr_dir = state.get("curr_dir")
        if not curr_dir:
            state_to_return["curr_dir"] = llm_answer['object_name']
        else:
            state_to_return["curr_dir"] = os.path.join(curr_dir, llm_answer['object_name'])
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
    """Создает новую директорию проекта в корневом рабочем пространстве.

    Этот узел отвечает за инициализацию нового проекта. Он извлекает
    имя проекта из состояния графа, формирует полный путь внутри
    пользовательского рабочего пространства (USER_WORKSPACE), проверяет,
    не существует ли уже такой проект, и создает для него папку.
    Результат операции (успех или неудача) возвращается в виде
    текстового сообщения для последующей озвучки.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поле
                            `curr_project` содержит имя проекта, которое
                            было извлечено LLM из команды пользователя.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce`, содержащий
              голосовой ответ для пользователя о результате создания проекта.
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
    """Клонирует Git-репозиторий по URL, извлеченному из команды пользователя.

    Этот узел активируется, когда пользователь хочет клонировать существующий
    проект из удаленного источника, такого как GitHub. Он извлекает URL
    репозитория и имя проекта из состояния, выполняет операцию `git clone`
    и формирует текстовый ответ для пользователя об успехе или неудаче операции.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поле
                            `curr_project` содержит имя для будущей папки,
                            а `transcribed_message` содержит URL репозитория.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce`, содержащий
              голосовой ответ для пользователя.
    """

    transcribed_message = state.get("transcribed_message")
    git_repo_url = llm_service.get_git_repo_url(transcribed_message)
    answer = project_tools.clone_project_from_github(git_repo_url, "projects/NEMO")
    if answer:
        return {"text_to_pronounce": "Project cloned from GitHub."}
    return {"text_to_pronounce": "Something went wrong."}


def create_directory_node(state: AgentState) -> Dict:
    """Создает новую директорию в текущем активном проекте.

    Узел отвечает за создание папок. Он конструирует полный путь,
    используя активный проект и имя новой директории из состояния.
    После попытки создания он возвращает текстовый ответ, который
    будет озвучен пользователю.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поля
                            `curr_project` и `curr_dir` заполнены.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce` с
              результатом операции.
    """
    directory_name = state.get("curr_dir")
    if not directory_name:
        return {"text_to_pronounce": "We couldn't define the directory name"}
    project_name = state.get("curr_project")
    dir_path = f"{USER_WORKSPACE}/{project_name}/{directory_name}"
    if os.path.exists(dir_path):
        return {"text_to_pronounce": f"Directory {directory_name} already exists."}

    created = dir_tools.create_directory(dir_path)
    if not created:
        return {"text_to_pronounce": f"Directory {directory_name} wasn't created."}
    return {"text_to_pronounce": f"Directory {directory_name} successfully created."}


def create_file_node(state: AgentState) -> Dict:
    """Создает новый пустой файл в текущей рабочей директории проекта.

    Этот узел обрабатывает команду создания файла. Он собирает полный путь
    к файлу из активного проекта, директории и имени файла, хранящихся
    в состоянии. Проверяет, не существует ли такой файл, и создает его,
    после чего формирует ответ для озвучивания.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поля
                            `curr_project`, `curr_dir` и `curr_file` заполнены.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce` с
              результатом операции.
    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get(
        "curr_dir"), state.get("curr_file")
    if not curr_file:
        return {"text_to_pronounce": "We couldn't define the file name"}
    filepath = f"{curr_project}/{curr_dir}/{curr_file}".replace("//", "/")
    filepath = os.path.join(USER_WORKSPACE, filepath)
    if os.path.exists(filepath):
        return {"text_to_pronounce": f"File {curr_file} already exists."}
    created = file_tools.create_file(filepath)
    if not created:
        return {"text_to_pronounce": f"File {filepath} wasn't created."}
    return {"text_to_pronounce": f"File {filepath} successfully created."}


def edit_file_node(state: AgentState) -> Dict:
    """Редактирует содержимое существующего файла на основе голосовой диктовки.

    Один из ключевых узлов, который позволяет писать код голосом. Он читает
    текущее содержимое файла, передает его вместе с транскрибированной
    командой пользователя в LLM для внесения изменений и перезаписывает
    файл новым содержимым.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поля
                            `curr_project`, `curr_dir`, `curr_file` и
                            `transcribed_message` заполнены.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce`,
              сообщающий об успехе или неудаче редактирования.
    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    filepath = f"{curr_project}/{curr_dir}/{curr_file}".replace("//", "/")
    filepath = os.path.join(USER_WORKSPACE, filepath)
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} does not exist."}
    transcribed_message = state.get("transcribed_message")
    existing_code = file_tools.read_file(filepath)
    new_content = llm_service.edit_file(existing_code, transcribed_message)
    edited = file_tools.edit_file(filepath, new_content)
    if not edited:
        return {"text_to_pronounce": f"Something went wrong editing {filepath}."}
    return {"text_to_pronounce": f"File {filepath} successfully edited."}


def run_file_node(state: AgentState) -> Dict:
    """Выполняет Python-скрипт и озвучивает результат его вывода.

    Этот узел отвечает за запуск кода. Он определяет путь к файлу на основе
    состояния, выполняет его как отдельный процесс, перехватывает
    стандартный вывод (stdout) и стандартный вывод ошибок (stderr),
    и формирует текстовый ответ, содержащий результат выполнения, для озвучки.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поля
                            `curr_project`, `curr_dir` и `curr_file` указывают
                            на существующий Python-файл.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce` с
              результатом выполнения скрипта.
    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    filepath = f"{curr_project}/{curr_dir}/{curr_file}".replace("//", "/")
    filepath = os.path.join(USER_WORKSPACE, filepath)
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} doesn't exist."}
    result = file_tools.run_file(filepath)
    if result:
        return {"text_to_pronounce": f"File was ran, and output is: {result}."}
    return {"text_to_pronounce": "Some troubles happened!"}


def get_file_content_node(state: AgentState) -> Dict:
    """Зачитывает и озвучивает полное содержимое указанного файла.

    Узел, реализующий функционал "чтения вслух". Он открывает файл,
    указанный в состоянии, считывает весь его текстовый контент и
    передает этот контент для последующей озвучки пользователю.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поля
                            `curr_project`, `curr_dir` и `curr_file`
                            указывают на существующий файл.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce`,
              содержащий полное содержимое файла.
    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    filepath = f"{curr_project}/{curr_dir}/{curr_file}".replace("//", "/")
    filepath = os.path.join(USER_WORKSPACE, filepath)
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} doesn't exist."}
    content = file_tools.read_file(filepath)
    if content == "not empty, but error":
        return {"text_to_pronounce": "Some troubles happened!"}
    if content == "":
        return {"text_to_pronounce": f"File {filepath} is empty"}
    return {"text_to_pronounce": f"System read file and content is: {content}"}


def summarize_file_content_node(state: AgentState) -> Dict:
    """Создает и озвучивает краткое содержание (summary) содержимого файла.

    Этот узел использует LLM для анализа текста. Он читает содержимое файла,
    отправляет его в языковую модель с задачей сделать краткий пересказ
    и возвращает сгенерированное summary для озвучки. Полезно для быстрой
    оценки больших файлов.

    Args:
        state (AgentState): Текущее состояние графа. Ожидается, что поля
                            `curr_project`, `curr_dir` и `curr_file`
                            указывают на существующий файл.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce`,
              содержащий краткое изложение содержимого файла.
    """
    curr_project, curr_dir, curr_file = state.get("curr_project"), state.get("curr_dir"), state.get("curr_file")
    filepath = f"{curr_project}/{curr_dir}/{curr_file}".replace("//", "/")
    filepath = os.path.join(USER_WORKSPACE, filepath)
    if not os.path.exists(filepath):
        return {"text_to_pronounce": f"File {filepath} doesn't exist."}
    content = file_tools.read_file(filepath)
    summary = llm_service.summarize_file_content(content)
    if not summary:
        return {"text_to_pronounce": "Some troubles happened!"}
    return {"text_to_pronounce": summary}


def unknown_operation_node(state: AgentState) -> Dict:
    """Обрабатывает случаи, когда намерение пользователя не было распознано.

    Это "запасной" узел, который активируется, если LLM не смог
    классифицировать команду пользователя ни под одну из известных операций.
    Он просто формирует вежливый ответ о том, что команда не понята,
    и передает его для озвучки.

    Args:
        state (AgentState): Текущее состояние графа.

    Returns:
        Dict: Словарь с обновлением для поля `text_to_pronounce` с
              сообщением об ошибке для пользователя.
    """
    return {"text_to_pronounce": "We couldn't understand your operation, maybe it hasn't implemented yet"}
