"""Azure Speech service wrapper for voice statement transcription."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from azure.identity import DefaultAzureCredential

from backend.core.config import get_settings
from backend.models.ingestion import VoiceTranscript

logger = logging.getLogger(__name__)

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None  # type: ignore[assignment]

# Languages from domain config for auto-detection
SUPPORTED_LANGUAGES = [
    "en-US", "es-ES", "fr-FR", "de-DE", "zh-CN",
    "ja-JP", "ko-KR", "pt-BR", "ar-SA", "hi-IN",
]


class SpeechService:
    """Wrapper around Azure Speech SDK for batch transcription of voice statements."""

    def __init__(
        self,
        endpoint: str | None = None,
        credential: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_speech_endpoint
        self._credential = credential or DefaultAzureCredential()

    async def transcribe_voice_statement(self, audio_path: str) -> VoiceTranscript:
        """Transcribe a voice statement from a local audio file.

        Args:
            audio_path: Path to a local audio file (WAV/MP3).

        Returns:
            VoiceTranscript with transcription text, detected language, and duration.

        Note:
            Phase 1 accepts local file paths only. Blob URL support will be added
            with the Durable Functions pipeline in Phase 2.
        """
        if speechsdk is None:
            raise RuntimeError("azure-cognitiveservices-speech is not installed")

        logger.info("Transcribing voice statement from %s", audio_path)

        speech_config = speechsdk.SpeechConfig(endpoint=self._endpoint)
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceConnection_LanguageIdMode,
            "Continuous",
        )

        auto_detect_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
            languages=SUPPORTED_LANGUAGES,
        )
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            auto_detect_source_language_config=auto_detect_config,
            audio_config=audio_config,
        )

        # The Speech SDK is synchronous; run in a thread to avoid blocking
        result = await asyncio.to_thread(recognizer.recognize_once)

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            detected_language = result.properties.get(
                speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult,
                "en-US",
            )
            # Duration is in 100-nanosecond ticks
            duration_seconds = 0.0
            try:
                # Try to get duration from result object
                duration_seconds = float(getattr(result, "duration", 0)) / 10_000_000
            except (ValueError, TypeError):
                pass

            return VoiceTranscript(
                original_text=result.text,
                detected_language=detected_language or "en-US",
                duration_seconds=duration_seconds,
                transcribed_at=datetime.utcnow(),
            )

        if result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning("No speech could be recognized in %s", audio_path)
            return VoiceTranscript(
                original_text="",
                detected_language="en-US",
                duration_seconds=0.0,
                transcribed_at=datetime.utcnow(),
            )

        # Canceled or error
        cancellation = result.cancellation_details
        raise RuntimeError(
            f"Speech recognition failed: {cancellation.reason} — {cancellation.error_details}"
        )
