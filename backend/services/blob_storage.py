"""Azure Blob Storage helper for claim file uploads."""

from __future__ import annotations

import logging
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas

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

        # Generate a SAS token so downstream services (Doc Intelligence, CU)
        # can download the blob without managed identity.
        try:
            sas_token = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self._container_name,
                blob_name=blob_name,
                snapshot=blob_client.snapshot,
                account_key=None,
                user_delegation_key=self._get_user_delegation_key(),
                permission="r",
                expiry=datetime.now(UTC) + timedelta(hours=1),
            )
            url = f"{blob_client.url}?{sas_token}"
        except Exception:
            # Fallback to plain URL if SAS generation fails
            url = blob_client.url

        logger.info("Uploaded %s → %s", filename, url)
        return url

    def _get_user_delegation_key(self):
        """Get a user delegation key for SAS generation using Entra ID."""
        client = self._get_client()
        start_time = datetime.now(UTC)
        expiry_time = start_time + timedelta(hours=1)
        return client.get_user_delegation_key(key_start_time=start_time, key_expiry_time=expiry_time)

    def download_blob_to_temp(self, blob_url: str) -> str:
        """Download a blob to a temporary local file.

        Args:
            blob_url: Full URL to the blob.

        Returns:
            Path to the temporary file. Caller is responsible for cleanup.
        """
        parsed = urlparse(blob_url)
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) < 2:
            raise ValueError(f"Cannot parse container/blob from URL: {blob_url}")
        container_name, blob_name = path_parts[0], path_parts[1]

        client = self._get_client()
        blob_client = client.get_blob_client(container_name, blob_name)

        suffix = "." + blob_name.rsplit(".", 1)[-1] if "." in blob_name else ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            stream = blob_client.download_blob()
            stream.readinto(tmp)
            tmp.flush()
        except Exception:
            tmp.close()
            raise
        tmp.close()

        logger.info("Downloaded %s → %s", blob_url, tmp.name)
        return tmp.name
