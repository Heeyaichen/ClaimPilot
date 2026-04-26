"""Unit tests for SpeechService with mocked Azure Speech SDK."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.speech import SpeechService


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "https://speech.example.com/")
    monkeypatch.setenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "")


def _patch_speechsdk():
    """Create a mock speechsdk module with all required attributes."""
    mock_speech = MagicMock()
    mock_speech.ResultReason.RecognizedSpeech = "RecognizedSpeech"
    mock_speech.ResultReason.NoMatch = "NoMatch"
    mock_speech.ResultReason.Canceled = "Canceled"
    mock_speech.PropertyId.SpeechServiceConnection_LanguageIdMode = "LanguageIdMode"
    mock_speech.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult = "AutoDetectResult"
    mock_speech.PropertyId.SpeechServiceResponse_RecognitionResult = "RecognitionResult"
    return mock_speech


def _make_recognized_result(
    text: str = "I was rear-ended at a stoplight.",
    detected_language: str = "en-US",
    duration: int = 50_000_000,
) -> MagicMock:
    """Create a mock result that looks like RecognizedSpeech."""
    result = MagicMock()
    result.reason = "RecognizedSpeech"
    result.text = text
    result.duration = duration
    result.properties = MagicMock()
    result.properties.get = MagicMock(return_value=detected_language)
    return result


def _make_no_match_result() -> MagicMock:
    """Create a mock result that looks like NoMatch."""
    result = MagicMock()
    result.reason = "NoMatch"
    return result


def _make_canceled_result() -> MagicMock:
    """Create a mock result that looks like Canceled."""
    result = MagicMock()
    result.reason = "Canceled"
    result.cancellation_details = MagicMock()
    result.cancellation_details.reason = "Error"
    result.cancellation_details.error_details = "Authentication failed"
    return result


@pytest.mark.asyncio
async def test_transcribe_english_passthrough(mock_settings: None) -> None:
    mock_result = _make_recognized_result(
        text="I was rear-ended at a stoplight on Main Street.",
        detected_language="en-US",
    )

    with patch("backend.services.speech.speechsdk", _patch_speechsdk()) as mock_speech:
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_once.return_value = mock_result
        mock_speech.SpeechRecognizer.return_value = mock_recognizer

        service = SpeechService(
            endpoint="https://speech.example.com/",
            credential=MagicMock(),
        )
        transcript = await service.transcribe_voice_statement("/tmp/test.wav")

    assert transcript.original_text == "I was rear-ended at a stoplight on Main Street."
    assert transcript.detected_language == "en-US"
    assert transcript.translated_text is None


@pytest.mark.asyncio
async def test_transcribe_with_language_detection(mock_settings: None) -> None:
    mock_result = _make_recognized_result(
        text="Tuve un accidente de coche ayer en la autopista.",
        detected_language="es-ES",
    )

    with patch("backend.services.speech.speechsdk", _patch_speechsdk()) as mock_speech:
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_once.return_value = mock_result
        mock_speech.SpeechRecognizer.return_value = mock_recognizer

        service = SpeechService(
            endpoint="https://speech.example.com/",
            credential=MagicMock(),
        )
        transcript = await service.transcribe_voice_statement("/tmp/test.wav")

    assert transcript.detected_language == "es-ES"
    assert "accidente" in transcript.original_text


@pytest.mark.asyncio
async def test_transcribe_no_match(mock_settings: None) -> None:
    mock_result = _make_no_match_result()

    with patch("backend.services.speech.speechsdk", _patch_speechsdk()) as mock_speech:
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_once.return_value = mock_result
        mock_speech.SpeechRecognizer.return_value = mock_recognizer

        service = SpeechService(
            endpoint="https://speech.example.com/",
            credential=MagicMock(),
        )
        transcript = await service.transcribe_voice_statement("/tmp/silent.wav")

    assert transcript.original_text == ""
    assert transcript.duration_seconds == 0.0


@pytest.mark.asyncio
async def test_transcribe_failure(mock_settings: None) -> None:
    mock_result = _make_canceled_result()

    with patch("backend.services.speech.speechsdk", _patch_speechsdk()) as mock_speech:
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_once.return_value = mock_result
        mock_speech.SpeechRecognizer.return_value = mock_recognizer

        service = SpeechService(
            endpoint="https://speech.example.com/",
            credential=MagicMock(),
        )

        with pytest.raises(RuntimeError, match="Speech recognition failed"):
            await service.transcribe_voice_statement("/tmp/test.wav")
