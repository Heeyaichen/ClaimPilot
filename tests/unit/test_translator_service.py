"""Unit tests for TranslatorService with mocked Azure SDK."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.models.ingestion import TranslationResult
from backend.services.translator import TranslatorService


def _make_mock_translation(translated_text: str = "I had a car accident") -> MagicMock:
    """Create a mock translation item."""
    translation = MagicMock()
    translation.text = translated_text
    translation.confidence = 0.95
    return translation


def _make_mock_response(translated_text: str = "I had a car accident") -> list:
    """Create a mock translation response (list)."""
    item = MagicMock()
    item.translations = [_make_mock_translation(translated_text)]
    return [item]


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_TRANSLATOR_ENDPOINT", "https://translator.example.com/")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "eastus2")
    monkeypatch.setenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "")


@pytest.mark.asyncio
async def test_translate_spanish_to_english(mock_settings: None) -> None:
    mock_response = _make_mock_response("I had a car accident yesterday on the highway.")

    with patch("backend.services.translator.TextTranslationClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.translate.return_value = mock_response

        service = TranslatorService(
            endpoint="https://translator.example.com/",
            region="eastus2",
            credential=MagicMock(),
        )
        result = await service.translate_to_english(
            "Tuve un accidente de coche ayer en la autopista.",
            "es-ES",
        )

    assert isinstance(result, TranslationResult)
    assert result.original_text == "Tuve un accidente de coche ayer en la autopista."
    assert result.translated_text == "I had a car accident yesterday on the highway."
    assert result.source_language == "es-ES"
    assert result.target_language == "en"
    # Verify the SDK was called (not a passthrough)
    mock_client.translate.assert_called_once()


@pytest.mark.asyncio
async def test_english_passthrough(mock_settings: None) -> None:
    """When source is English, no API call should be made."""
    with patch("backend.services.translator.TextTranslationClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value

        service = TranslatorService(
            endpoint="https://translator.example.com/",
            region="eastus2",
            credential=MagicMock(),
        )
        result = await service.translate_to_english(
            "I was in an accident.",
            "en-US",
        )

    assert result.translated_text == "I was in an accident."
    assert result.source_language == "en-US"
    assert result.confidence == 1.0
    # Verify no API call was made
    mock_client.translate.assert_not_called()


@pytest.mark.asyncio
async def test_english_variant_passthrough(mock_settings: None) -> None:
    """Any English variant (en, en-GB, en-AU) should pass through."""
    with patch("backend.services.translator.TextTranslationClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value

        service = TranslatorService(
            endpoint="https://translator.example.com/",
            region="eastus2",
            credential=MagicMock(),
        )
        result = await service.translate_to_english("I had a crash.", "en-GB")

    assert result.translated_text == "I had a crash."
    mock_client.translate.assert_not_called()


@pytest.mark.asyncio
async def test_translate_failure(mock_settings: None) -> None:
    from azure.core.exceptions import HttpResponseError

    with patch("backend.services.translator.TextTranslationClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.translate.side_effect = HttpResponseError("Service unavailable", status_code=503)

        service = TranslatorService(
            endpoint="https://translator.example.com/",
            region="eastus2",
            credential=MagicMock(),
        )

        with pytest.raises(HttpResponseError):
            await service.translate_to_english("Bonjour le monde", "fr-FR")


@pytest.mark.asyncio
async def test_translate_empty_response(mock_settings: None) -> None:
    with patch("backend.services.translator.TextTranslationClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.translate.return_value = []

        service = TranslatorService(
            endpoint="https://translator.example.com/",
            region="eastus2",
            credential=MagicMock(),
        )

        with pytest.raises(ValueError, match="Translation returned empty response"):
            await service.translate_to_english("Bonjour", "fr-FR")
