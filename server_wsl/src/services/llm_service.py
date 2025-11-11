from ..core.logger_config import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from .llm_answer_schemas import ChooseOperationAndGetFilename
from langchain_community.tools.tavily_search import TavilySearchResults
import os

load_dotenv()


class GeminiService:
    """
    Сервис для инкапсуляции всей логики работы с Google Gemini API через LangChain.
    """
    _instance = None  # Атрибут класса для хранения единственного экземпляра

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            logger.info("Создание нового (и единственного) экземпляра GeminiService...")
            cls._instance = super(GeminiService, cls).__new__(cls)
        else:
            logger.info("Возвращение существующего экземпляра GeminiService...")
        return cls._instance

    def __init__(self, model_name: str = "gemini-2.5-flash", temperature: float = 0.7):
        """
        Инициализирует сервис, загружает API-ключ и настраивает модель.

        Args:
            model_name (str): Название модели Gemini для использования.
            temperature (float): "Креативность" модели. От 0.0 до 1.0.
        """
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("Не найден GEMINI_API_KEY. Убедитесь, что он есть в .env файле.")

        tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not tavily_api_key:
            raise ValueError("Не найден TAVILY_API_KEY. Убедитесь, что он есть в .env файле.")

        try:
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=gemini_api_key,
                temperature=temperature,
                convert_system_message_to_human=True
            )

            self.search = TavilySearchResults(max_results=3)
            logger.info(f"Сервис Gemini успешно инициализирован с моделью {model_name} и поиском Tavily")
        except Exception as e:
            logger.error(f"Ошибка при инициализации сервисов: {e}")
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
                "If the operation involves a project, the `object_name` must be in PascalCase. Each word starts with a capital letter, with no spaces"
                "If the operation involves a file or a folder, the `object_name` must be in snake_case. All letters are lowercase, and words are separated by underscores"
                "Remember that, after dot it is oftenly is using .py .txt or extensions like this"
                "Return the result ONLY in JSON format. "
                "Do not add any explanations or ```json``` wrappers.\n\n{format_instructions}"
            ),
            # --- НАЧАЛО ПРИМЕРОВ (FEW-SHOT EXAMPLES) ---
            (
                "human",
                "create a project named big races"
            ),
            (
                "ai",
                '{{"operation": "create project", "object_name": "BigRaces"}}'
            ),
            (
                "human",
                "write the code Hello to index dot html"
            ),
            (
                "ai",
                '{{"operation": "edit file", "object_name": "index.html"}}'
            ),
            (
                "human",
                "run the script test files dot py"
            ),
            (
                "ai",
                '{{"operation": "run file", "object_name": "test_files.py"}}'
            ),
            (
                "human",
                "hi, how are you?"
            ),
            (
                "ai",
                # Важно иметь пример для случая, когда команда не распознана
                '{{"operation": "unknown", "object_name": null}}'
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

    def summarize_file_content(self, content: str) -> str:
        """
        Пишет краткое содержимое файла
        """
        prompt = f"Please read this file and summarize it's content: '{content}'"
        response = self.llm.invoke(prompt)
        return response

    def edit_file(self, existing_code: str, transcribed_message: str) -> str:
        """
        На основе существующего кода и правок со стороны юзера, должен
        понять как должен выглядеть финальный вариант кода
        """
        template = """
        You are a highly precise code editing engine. Your sole purpose is to take existing code and apply a series of spoken instructions to it.

        You MUST interpret the following spoken commands as formatting instructions:
        - "enter": Insert a newline character (\n).
        - "tab": Insert an indentation (4 spaces).
        - "colon": Insert a colon character (:).
        # Добавьте другие команды по необходимости, например:
        # - "backspace": Delete the previous character.
        # - "delete line": Delete the entire current line.

        Follow these steps:
        1. Analyze the existing code.
        2. Carefully process the user's spoken instructions, applying the special formatting commands listed above.
        3. Integrate the new code and formatting changes into the existing code.

        Your output MUST be ONLY the complete, final code. Do not include any explanations, comments about your work, or markdown code fences like ```python.

        ### EXISTING CODE:
        {existing_code}

        ### USER'S SPOKEN INSTRUCTIONS:
        {transcribed_message}

        ### FINAL FULL CODE:
        """

        prompt = template.format(
            existing_code=existing_code,
            transcribed_message=transcribed_message
        )
        answer = self.llm.invoke(prompt)
        return answer

    def get_git_repo_url(self, transcribed_message: str) -> str:
        """
        Извлекает URL .git репозитория, используя трехэтапный процесс:
        1. Перефразирование запроса для поиска.
        2. Поиск с помощью Tavily.
        3. Извлечение URL из результатов поиска.
        """
        logger.info(f"Начинаю 3-этапный поиск URL для запроса: '{transcribed_message}'")

        # --- ЭТАП 1: Создание чистого поискового запроса ---
        query_generation_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at refining user requests into precise search engine queries. "
                       "Extract only the key entities like project names, companies, and technologies. "
                       "Your output must be ONLY the search query text and nothing else."),
            ("human", "User request: '{user_request}'\n\nRefined search query:")
        ])

        query_generation_chain = query_generation_prompt | self.llm | StrOutputParser()

        try:
            generated_query = query_generation_chain.invoke({"user_request": transcribed_message})
            logger.info(f"Сгенерирован поисковый запрос: '{generated_query}'")
        except Exception as e:
            logger.error(f"Ошибка на этапе генерации поискового запроса: {e}")
            return "Error: Could not generate search query."

        # --- ЭТАП 2: Поиск информации с помощью Tavily ---
        try:
            search_results = self.search.invoke({"query": generated_query})
            logger.info("Результаты поиска Tavily успешно получены.")
        except Exception as e:
            logger.error(f"Ошибка во время выполнения поиска Tavily: {e}")
            return "Error: Could not perform search."

        # --- ЭТАП 3: Извлечение финального ответа из контекста ---
        extraction_prompt = ChatPromptTemplate.from_template(
            """
            You are a highly intelligent assistant specializing in analyzing search results to find specific information.
            Based on the user's original request and the provided search results, find the correct GitHub repository clone URL.

            **Original User Request:**
            {original_request}

            **Generated Search Query:**
            {generated_query}

            **Search Results from Tavily:**
            {search_context}

            ---
            Your task is to return ONLY the full clone URL that ends with '.git'.
            If no suitable URL is found, return the exact string 'Could not find the repository URL.'.
            Do not add any explanations or introductory text.

            Final Git Clone URL:
            """
        )

        extraction_chain = extraction_prompt | self.llm | StrOutputParser()

        try:
            final_url = extraction_chain.invoke({
                "original_request": transcribed_message,
                "generated_query": generated_query,
                "search_context": search_results
            })
            logger.info(f"Модель извлекла финальный URL: '{final_url}'")
            return final_url.strip()
        except Exception as e:
            logger.error(f"Ошибка на этапе извлечения URL из результатов поиска: {e}")
            return "Error: Could not process search results."
