"""Unit tests for DocumentIntelligenceService with mocked Azure SDK."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.models.ingestion import DocumentExtractionResult
from backend.services.document_intelligence import (
    DocumentIntelligenceService,
    EmptyDocumentError,
)


def _make_mock_field(
    value_string: str | None = None,
    value_number: float | None = None,
    confidence: float = 0.95,
    content: str = "",
) -> MagicMock:
    """Create a mock Document Intelligence field."""
    field = MagicMock()
    field.value_string = value_string
    field.value_number = value_number
    field.value_boolean = None
    field.value_date = None
    field.content = content or value_string or str(value_number)
    field.confidence = confidence
    field.bounding_regions = []
    return field


def _make_mock_result(
    documents: list[dict[str, Any]] | None = None,
    content: str = "# Extracted Form\nPolicy: AB12345678",
    pages_count: int = 2,
) -> MagicMock:
    """Create a mock AnalyzeResult."""
    result = MagicMock()
    result.content = content
    result.pages = [MagicMock()] * pages_count

    if documents is None:
        doc = MagicMock()
        doc.fields = {
            "policy_number": _make_mock_field(value_string="AB12345678", confidence=0.98),
            "applicant_name": _make_mock_field(value_string="John Smith", confidence=0.92),
        }
        result.documents = [doc]
    elif len(documents) == 0:
        result.documents = []
    else:
        mock_docs = []
        for doc_data in documents:
            doc = MagicMock()
            doc.fields = {
                name: _make_mock_field(**field_data)
                for name, field_data in doc_data.items()
            }
            mock_docs.append(doc)
        result.documents = mock_docs

    return result


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "https://di.example.com/")
    monkeypatch.setenv("AZURE_DOC_INTELLIGENCE_MODEL_ID", "test-model")
    monkeypatch.setenv("AZURE_SPEECH_ENDPOINT", "")


@pytest.mark.asyncio
async def test_extract_claim_form_success(mock_settings: None) -> None:
    mock_result = _make_mock_result()
    mock_poller = MagicMock()
    mock_poller.result.return_value = mock_result

    with patch("backend.services.document_intelligence.DocumentIntelligenceClient") as mock_client_cls:
        mock_client_instance = mock_client_cls.return_value
        mock_client_instance.begin_analyze_document.return_value = mock_poller

        service = DocumentIntelligenceService(
            endpoint="https://di.example.com/",
            model_id="test-model",
            credential=MagicMock(),
        )
        result = await service.extract_claim_form("https://blob.example.com/form.pdf")

    assert isinstance(result, DocumentExtractionResult)
    assert result.model_id == "test-model"
    assert result.pages == 2
    assert "policy_number" in result.fields
    assert result.fields["policy_number"].value == "AB12345678"
    assert result.fields["policy_number"].confidence == 0.98


@pytest.mark.asyncio
async def test_extract_claim_form_empty_document(mock_settings: None) -> None:
    mock_result = _make_mock_result(documents=[])
    mock_poller = MagicMock()
    mock_poller.result.return_value = mock_result

    with patch("backend.services.document_intelligence.DocumentIntelligenceClient") as mock_client_cls:
        mock_client_instance = mock_client_cls.return_value
        mock_client_instance.begin_analyze_document.return_value = mock_poller

        service = DocumentIntelligenceService(
            endpoint="https://di.example.com/",
            model_id="test-model",
            credential=MagicMock(),
        )

        with pytest.raises(EmptyDocumentError, match="No documents found"):
            await service.extract_claim_form("https://blob.example.com/empty.pdf")


@pytest.mark.asyncio
async def test_extract_claim_form_fields_mapping(mock_settings: None) -> None:
    custom_docs = [
        {
            "policy_number": {"value_string": "XY99999999", "confidence": 0.99},
            "repair_amount": {"value_number": 8400.50, "confidence": 0.87},
            "loss_date": {"content": "2026-01-15", "confidence": 0.91},
        }
    ]
    mock_result = _make_mock_result(documents=custom_docs)
    mock_poller = MagicMock()
    mock_poller.result.return_value = mock_result

    with patch("backend.services.document_intelligence.DocumentIntelligenceClient") as mock_client_cls:
        mock_client_instance = mock_client_cls.return_value
        mock_client_instance.begin_analyze_document.return_value = mock_poller

        service = DocumentIntelligenceService(
            endpoint="https://di.example.com/",
            model_id="test-model",
            credential=MagicMock(),
        )
        result = await service.extract_claim_form("https://blob.example.com/form.pdf")

    assert result.fields["policy_number"].value == "XY99999999"
    assert result.fields["repair_amount"].value == 8400.50
    assert result.fields["loss_date"].value == "2026-01-15"


@pytest.mark.asyncio
async def test_extract_claim_form_http_error(mock_settings: None) -> None:
    from azure.core.exceptions import HttpResponseError

    with patch("backend.services.document_intelligence.DocumentIntelligenceClient") as mock_client_cls:
        mock_client_instance = mock_client_cls.return_value
        mock_client_instance.begin_analyze_document.side_effect = HttpResponseError(
            "Service unavailable", status_code=503
        )

        service = DocumentIntelligenceService(
            endpoint="https://di.example.com/",
            model_id="test-model",
            credential=MagicMock(),
        )

        with pytest.raises(HttpResponseError):
            await service.extract_claim_form("https://blob.example.com/form.pdf")
