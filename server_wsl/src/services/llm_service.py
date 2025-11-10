from ..core.logger_config import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from llm_answer_schemas import ChooseOperationAndGetFilename
import os

load_dotenv()


class GeminiService:
    """
    Сервис для инкапсуляции всей логики работы с Google Gemini API через LangChain.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.7):
        """
        Инициализирует сервис, загружает API-ключ и настраивает модель.

        Args:
            model_name (str): Название модели Gemini для использования.
            temperature (float): "Креативность" модели. От 0.0 до 1.0.
        """
        load_dotenv()  # Загружаем переменные из .env файла
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Не найден GEMINI_API_KEY. Убедитесь, что он есть в .env файле.")

        try:
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
                temperature=temperature,
                convert_system_message_to_human=True  # Для лучшей совместимости
            )
            logger.info(f"Сервис Gemini успешно инициализирован с моделью {model_name}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации модели Gemini: {e}")
            raise

    def choose_operation(self, message: str) -> dict:
        """
        Определяет намерение пользователя и извлекает данные, используя few-shot prompting.
        """
        parser = JsonOutputParser(pydantic_object=ChooseOperationAndGetFilename)

        # Создаем ChatPromptTemplate со списком сообщений
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are an intelligent command router. Your task is to analyze the user's request "
                "and determine which operation they want to perform and the name of the project, folder, or file. "
                "Return the result ONLY in JSON format. "
                "Do not add any explanations or ```json``` wrappers.\n\n{format_instructions}"
            ),
            # --- НАЧАЛО ПРИМЕРОВ (FEW-SHOT EXAMPLES) ---
            (
                "human",
                "create a file named main.py"
            ),
            (
                "ai",
                '{"operation": "create file", "object_name": "main.py"}'
            ),
            (
                "human",
                "write the code <h1>Hello</h1> to index.html"
            ),
            (
                "ai",
                '{"operation": "edit file", "object_name": "index.html"}'
            ),
            (
                "human",
                "run the script test.py"
            ),
            (
                "ai",
                '{"operation": "run file", "object_name": "test.py"}'
            ),
            (
                "human",
                "hi, how are you?"
            ),
            (
                "ai",
                # Важно иметь пример для случая, когда команда не распознана
                '{"operation": "unknown", "object_name": null}'
            ),
            # --- КОНЕЦ ПРИМЕРОВ ---
            (
                "human",
                "{message}"  # Здесь будет реальный запрос пользователя
            )
        ])

        # Собираем цепочку (chain)
        chain = prompt | self.llm | parser

        # Вызываем цепочку
        result = chain.invoke({
            "message": message,
            "format_instructions": parser.get_format_instructions()
        })

        return result
