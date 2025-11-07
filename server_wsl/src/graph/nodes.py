import os
from typing import Dict
from .state import AgentState
from ..services.asr_service import TranscriptionService
from ..services.tts_service import TextToSpeechService
from ..core.logger_config import logger


logger.info("Загружаем ASR модель")
asr_service = TranscriptionService()
logger.info("Экземпляр TranscriptionService создан.")

logger.info("Загружаем TTS модель")
tts_service = TextToSpeechService()
logger.info("Экземпляр TextToSpeechService создан.")

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
