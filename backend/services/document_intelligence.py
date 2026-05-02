"""Azure Document Intelligence service wrapper for ACORD form extraction."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.identity import DefaultAzureCredential

from backend.core.config import get_settings
from backend.models.ingestion import DocumentExtractionResult, DocumentField

logger = logging.getLogger(__name__)


class EmptyDocumentError(Exception):
    """Raised when Document Intelligence returns no documents in the result."""


class DocumentIntelligenceService:
    """Async wrapper around Azure Document Intelligence for claim form extraction."""

    def __init__(
        self,
        endpoint: str | None = None,
        model_id: str | None = None,
        credential: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_doc_intelligence_endpoint
        self._model_id = model_id or settings.azure_doc_intelligence_model_id
        self._credential = credential or DefaultAzureCredential()
        self._client = DocumentIntelligenceClient(
            endpoint=self._endpoint,
            credential=self._credential,
        )

    def _extract_field_value(self, field: Any) -> str | int | float | bool | None:
        """Extract the typed value from a Document Intelligence field."""
        if field.value_string is not None:
            return str(field.value_string)
        if field.value_number is not None:
            return float(field.value_number)
        if field.value_boolean is not None:
            return bool(field.value_boolean)
        if field.value_date is not None:
            return str(field.value_date)
        return str(field.content) if field.content else None

    async def extract_claim_form(self, blob_url: str) -> DocumentExtractionResult:
        """Extract structured fields from a claim form at the given blob URL.

        Args:
            blob_url: URL to the PDF/image in Azure Blob Storage.

        Returns:
            DocumentExtractionResult with markdown content and extracted fields.

        Raises:
            EmptyDocumentError: If no documents are found in the result.
            HttpResponseError: On Azure service errors.
        """
        logger.info("Extracting claim form from %s with model %s", blob_url, self._model_id)

        poller = self._client.begin_analyze_document(
            model_id=self._model_id,
            body=AnalyzeDocumentRequest(url_source=blob_url),
            output_content_format="markdown",
        )
        result = await asyncio.to_thread(poller.result)

        if not result.documents:
            # prebuilt-layout and prebuilt-read return content but no documents
            # Return extracted text without structured fields
            if result.content:
                logger.info(
                    "No structured documents found, returning raw content (%d pages)",
                    len(result.pages) if result.pages else 0,
                )
                return DocumentExtractionResult(
                    markdown_content=result.content,
                    fields={},
                    model_id=self._model_id,
                    pages=len(result.pages) if result.pages else 0,
                    extracted_at=datetime.utcnow(),
                )
            raise EmptyDocumentError(f"No documents found in analysis result for {blob_url}")

        doc = result.documents[0]
        fields: dict[str, DocumentField] = {}
        for name, field in (doc.fields or {}).items():
            fields[name] = DocumentField(
                value=self._extract_field_value(field),
                confidence=field.confidence if field.confidence is not None else 0.0,
                bounding_regions=[{"page": getattr(br, "page", 0)} for br in (field.bounding_regions or [])],
            )

        return DocumentExtractionResult(
            markdown_content=result.content or "",
            fields=fields,
            model_id=self._model_id,
            pages=len(result.pages) if result.pages else 0,
            extracted_at=datetime.utcnow(),
        )
