"""Azure Blob Storage helper for claim file uploads."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

CONTAINER_NAME = "claims-intake"


class BlobStorageService:
    """Uploads claim files to Azure Blob Storage."""

    def __init__(
        self,
        endpoint: str | None = None,
        credential: Any | None = None,
        container_name: str = CONTAINER_NAME,
    ) -> None:
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_storage_endpoint
        self._credential = credential or DefaultAzureCredential()
        self._container_name = container_name

    def _get_client(self) -> BlobServiceClient:
        return BlobServiceClient(
            account_url=self._endpoint, credential=self._credential
        )

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        claim_id: str | None = None,
        prefix: str = "",
    ) -> str:
        """Upload a file and return its blob URL.

        Args:
            file_data: Raw file bytes.
            filename: Original filename.
            claim_id: Optional claim ID for blob path organization.
            prefix: Optional prefix (e.g., 'images', 'audio').

        Returns:
            Full blob URL of the uploaded file.
        """
        blob_id = uuid.uuid4().hex[:8]
        parts = [prefix, claim_id, f"{blob_id}_{filename}"] if claim_id else [prefix, f"{blob_id}_{filename}"]
        blob_name = "/".join(p for p in parts if p)

        client = self._get_client()
        container = client.get_container_client(self._container_name)
        blob_client = container.get_blob_client(blob_name)
        blob_client.upload_blob(file_data, overwrite=True)

        url = blob_client.url
        logger.info("Uploaded %s → %s", filename, url)
        return url
