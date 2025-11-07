import torch
import nemo.collections.asr as nemo_asr
from pathlib import Path
from typing import Union
from ..core.logger_config import logger


class TranscriptionService:
    """
    Сервис-одиночка (Singleton) для транскрибации аудио с использованием моделей NVIDIA NeMo.
    Гарантирует, что в приложении существует только один экземпляр этого класса.
    """
    _instance = None  # Атрибут класса для хранения единственного экземпляра

    def __new__(cls, *args, **kwargs):
        # __new__ отвечает за создание объекта
        if not cls._instance:
            logger.info("Создание нового (и единственного) экземпляра TranscriptionService...")
            cls._instance = super(TranscriptionService, cls).__new__(cls)
        else:
            logger.info("Возвращение существующего экземпляра TranscriptionService...")
        return cls._instance

    def __init__(self, model_name: str = "QuartzNet15x5Base-En"):
        """
        Инициализирует сервис транскрибации.
        Благодаря проверке, тяжелая логика выполнится только один раз.
        """
        # Проверяем, был ли объект уже инициализирован
        if hasattr(self, '_initialized') and self._initialized:
            return

        logger.info("Первичная инициализация TranscriptionService (загрузка модели)...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Используется устройство: {self.device}")

        try:
            self.asr_model = nemo_asr.models.ASRModel.from_pretrained(model_name=model_name)
            self.asr_model.to(self.device)
            logger.info(f"ASR модель '{model_name}' успешно загружена.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке ASR модели: {e}")
            self.asr_model = None

        # Ставим флаг, что инициализация завершена
        self._initialized = True

    def transcribe(self, audio_filepath: Union[str, Path]) -> str:
        if not self.asr_model:
            logger.warning("ASR модель недоступна. Транскрибация невозможна.")
            return ""

        audio_path_str = str(audio_filepath)
        logger.info(f"Транскрибация файла: {audio_path_str}...")
        try:
            transcriptions = self.asr_model.transcribe([audio_path_str])
            return transcriptions[0].text
        except Exception as e:
            logger.error(f"Произошла ошибка во время транскрибации: {e}")
            return ""
