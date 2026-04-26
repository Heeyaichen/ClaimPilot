"""Azure Translator service wrapper for text translation."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from azure.ai.translation.text import TextTranslationClient
from azure.identity import DefaultAzureCredential

from backend.core.config import get_settings
from backend.models.ingestion import TranslationResult

logger = logging.getLogger(__name__)


class TranslatorService:
    """Wrapper around Azure Translator for text translation to English."""

    def __init__(
        self,
        endpoint: str | None = None,
        region: str | None = None,
        credential: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_translator_endpoint
        self._region = region or settings.azure_translator_region
        self._credential = credential or DefaultAzureCredential()
        self._client = TextTranslationClient(
            endpoint=self._endpoint,
            credential=self._credential,
            region=self._region,
        )

    async def translate_to_english(
        self,
        text: str,
        source_language: str,
    ) -> TranslationResult:
        """Translate text to English.

        Args:
            text: Source text to translate.
            source_language: BCP-47 language tag of the source text.

        Returns:
            TranslationResult with original and translated text.

        Note:
            If source_language starts with "en", returns text as-is without
            making an API call.
        """
        logger.info("Translating text from %s to en", source_language)

        # Passthrough for English — no API call needed
        if source_language.startswith("en"):
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language="en",
                confidence=1.0,
                translated_at=datetime.utcnow(),
            )

        # The TextTranslationClient translate method is synchronous
        def _translate() -> list:
            return self._client.translate(  # type: ignore[no-any-return]
                body=[text],
                from_language=source_language,
                to_language=["en"],
            )

        response = await asyncio.to_thread(_translate)

        if not response:
            raise ValueError(f"Translation returned empty response for '{text[:50]}'")

        translation = response[0]
        translated_text = translation.translations[0].text if translation.translations else text
        confidence = 1.0
        if translation.translations:
            confidence = getattr(translation.translations[0], "confidence", 1.0) or 1.0

        return TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=source_language,
            target_language="en",
            confidence=confidence,
            translated_at=datetime.utcnow(),
        )
