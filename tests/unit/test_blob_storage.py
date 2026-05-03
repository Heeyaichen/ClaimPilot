"""Unit tests for BlobStorageService — mocked Azure SDK."""

from unittest.mock import MagicMock

from backend.services.blob_storage import BlobStorageService


def _make_service() -> tuple[BlobStorageService, MagicMock]:
    """Create a BlobStorageService with a mocked BlobServiceClient."""
    mock_blob_client = MagicMock()
    mock_blob_client.url = "https://storage.blob.core.windows.net/claims-intake/forms/test_doc.pdf"
    mock_blob_client.upload_blob.return_value = None

    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client

    mock_service_client = MagicMock()
    mock_service_client.get_container_client.return_value = mock_container

    service = BlobStorageService.__new__(BlobStorageService)
    service._endpoint = "https://storage.blob.core.windows.net"
    service._credential = MagicMock()
    service._container_name = "claims-intake"
    service._get_client = MagicMock(return_value=mock_service_client)

    return service, mock_blob_client


def test_upload_file_returns_url():
    service, mock_blob = _make_service()
    url = service.upload_file(b"file content", "doc.pdf", claim_id="c1", prefix="forms")
    assert url == mock_blob.url
    assert service._get_client.call_count >= 1


def test_upload_file_without_claim_id():
    service, _ = _make_service()
    url = service.upload_file(b"content", "img.jpg", prefix="images")
    assert "claims-intake" in url
