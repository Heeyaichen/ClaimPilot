"""Unit tests for backend.core.config."""


import pytest


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "https://example.cognitiveservices.azure.com/")
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "https://example.api.cognitive.microsoft.com/")
    monkeypatch.setenv("AZURE_TRANSLATOR_REGION", "westus2")

    from backend.core.config import Settings

    s = Settings()
    assert s.azure_doc_intelligence_endpoint == "https://example.cognitiveservices.azure.com/"
    assert s.azure_speech_endpoint == "https://example.api.cognitive.microsoft.com/"
    assert s.azure_translator_region == "westus2"


def test_settings_defaults() -> None:
    from backend.core.config import Settings

    s = Settings(azure_doc_intelligence_endpoint="", azure_speech_endpoint="")
    assert s.azure_doc_intelligence_model_id == "prebuilt-document"
    assert s.azure_translator_endpoint == "https://api.cognitive.microsofttranslator.com/"
    assert s.azure_translator_region == "eastus2"
    assert s.foundry_model_deployment == "gpt-5-4"


def test_get_settings_returns_settings() -> None:
    from backend.core.config import Settings, get_settings

    result = get_settings()
    assert isinstance(result, Settings)


def test_settings_ignores_extra_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_UNRELATED_VAR", "value")
    from backend.core.config import Settings

    s = Settings(azure_doc_intelligence_endpoint="", azure_speech_endpoint="")
    assert not hasattr(s, "some_unrelated_var")
