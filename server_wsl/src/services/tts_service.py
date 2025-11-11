import torch
from nemo.collections.tts.models import FastPitchModel
from nemo.collections.tts.models import HifiGanModel
from pathlib import Path
from typing import Union, Optional
import soundfile as sf
from ..core.logger_config import logger


class TextToSpeechService:
    """
    Сервис-одиночка (Singleton) для синтеза речи из текста (TTS).
    Использует модели FastPitch и HiFi-GAN из NVIDIA NeMo для английского языка.
    Гарантирует, что в приложении существует только один экземпляр этого класса.
    """
    _instance = None  # Атрибут класса для хранения единственного экземпляра

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            logger.info("Создание нового (и единственного) экземпляра TextToSpeechService...")
            cls._instance = super(TextToSpeechService, cls).__new__(cls)
        else:
            logger.info("Возвращение существующего экземпляра TextToSpeechService...")
        return cls._instance

    def __init__(self, spec_generator: str = "tts_en_fastpitch", model: str = "nvidia/tts_hifigan"):
        """
        Инициализирует сервис синтеза речи.
        Загрузка модели происходит только один раз при первом создании объекта.
        """
        # Проверяем, был ли объект уже инициализирован
        if hasattr(self, '_initialized') and self._initialized:
            return

        logger.info("Первичная инициализация TextToSpeechService (загрузка модели)...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Используется устройство: {self.device}")

        self.model = None
        self.spec_generator = None
        try:
            self.spec_generator = FastPitchModel.from_pretrained(spec_generator)
            self.model = HifiGanModel.from_pretrained(model)
            self.spec_generator.to(self.device)
            self.model.to(self.device)
            self.spec_generator.eval()
            self.model.eval()
            logger.info(f"TTS модели '{spec_generator}' и '{model}' успешно загружены.")
        except Exception as e:
            logger.error(f"Ошибка при загрузке TTS модели: {e}")

        # Ставим флаг, что инициализация завершена
        self._initialized = True

    def synthesize(self, text: str, output_filepath: Union[str, Path]) -> Optional[str]:
        """
        Синтезирует речь из текста и сохраняет ее в аудиофайл.

        Args:
            text (str): Текст, который необходимо озвучить.
            output_filepath (Union[str, Path]): Путь для сохранения .wav файла.

        Returns:
            Optional[str]: Строковый путь к созданному аудиофайлу в случае успеха, иначе None.
        """
        if not self.model:
            logger.warning("TTS модель недоступна. Синтез речи невозможен.")
            return None

        output_path_str = str(output_filepath)
        logger.info(f"Синтез речи для текста: '{text}'")

        try:
            parsed = self.spec_generator.parse(text)
            spectrogram = self.spec_generator.generate_spectrogram(tokens=parsed)
            audio = self.model.convert_spectrogram_to_audio(spec=spectrogram)
            sf.write(output_filepath, audio.to('cpu').detach().numpy()[0], 22050)
            logger.info(f"Аудиофайл успешно сохранен: {output_path_str}")
            return output_path_str

        except Exception as e:
            logger.error(f"Произошла ошибка во время синтеза речи: {e}")
            return None


