"""Unit tests for ContentUnderstandingService with mocked httpx."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.models.ingestion import ImageAnalysisResult
from backend.services.content_understanding import ContentUnderstandingService

MOCK_SUCCESS_RESPONSE = {
    "result": {
        "damage_indicators": [
            {"panel": "front", "severity": "moderate", "description": "Front bumper deformation"},
            {"panel": "front", "severity": "minor", "description": "Headlight housing crack"},
        ],
        "vehicle_identification": {
            "make": "Toyota",
            "model": "Camry",
            "year": 2022,
            "color": "Silver",
            "license_plate_visible": True,
            "license_plate_value": "ABC-1234",
        },
        "scene_conditions": {
            "time_of_day_estimated": "afternoon",
            "weather_conditions": "clear",
            "location_type": "parking_lot",
        },
        "forensic_flags": [],
    }
}


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_CONTENT_UNDERSTANDING_ENDPOINT", "https://cu.example.com/api/")
    monkeypatch.setenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "")


@pytest.mark.asyncio
async def test_analyze_image_success(mock_settings: None) -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = MOCK_SUCCESS_RESPONSE
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_credential = MagicMock()
    mock_token = MagicMock()
    mock_token.token = "fake-token"
    mock_credential.get_token = AsyncMock(return_value=mock_token)

    with patch("backend.services.content_understanding.httpx.AsyncClient", return_value=mock_client):
        service = ContentUnderstandingService(
            endpoint="https://cu.example.com/api/",
            credential=mock_credential,
        )
        result = await service.analyze_accident_image("https://example.com/photo.jpg")

    assert isinstance(result, ImageAnalysisResult)
    assert len(result.damage_indicators) == 2
    assert result.damage_indicators[0].panel == "front"
    assert result.damage_indicators[0].severity == "moderate"
    assert result.vehicle_identification.make == "Toyota"
    assert result.vehicle_identification.model == "Camry"
    assert result.scene_conditions.location_type == "parking_lot"


@pytest.mark.asyncio
async def test_analyze_image_malformed_response(mock_settings: None) -> None:
    malformed_response = {"not_the_expected_key": "unexpected_value"}
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = malformed_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_credential = MagicMock()
    mock_token = MagicMock()
    mock_token.token = "fake-token"
    mock_credential.get_token = AsyncMock(return_value=mock_token)

    with patch("backend.services.content_understanding.httpx.AsyncClient", return_value=mock_client):
        service = ContentUnderstandingService(
            endpoint="https://cu.example.com/api/",
            credential=mock_credential,
        )
        result = await service.analyze_accident_image("https://example.com/photo.jpg")

    # Should return a result with empty defaults for missing fields
    assert isinstance(result, ImageAnalysisResult)
    assert result.damage_indicators == []


@pytest.mark.asyncio
async def test_analyze_image_service_error(mock_settings: None) -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=mock_response
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_credential = MagicMock()
    mock_token = MagicMock()
    mock_token.token = "fake-token"
    mock_credential.get_token = AsyncMock(return_value=mock_token)

    with patch("backend.services.content_understanding.httpx.AsyncClient", return_value=mock_client):
        service = ContentUnderstandingService(
            endpoint="https://cu.example.com/api/",
            credential=mock_credential,
        )

        with pytest.raises(httpx.HTTPStatusError):
            await service.analyze_accident_image("https://example.com/photo.jpg")


def test_schema_loading() -> None:
    """Verify the extraction schema file exists and loads correctly."""
    schema_path = (
        Path(__file__).resolve().parent.parent.parent
        / "backend" / "domains" / "auto_damage" / "extraction_schema.json"
    )
    assert schema_path.exists(), f"Schema file not found at {schema_path}"

    from backend.services.content_understanding import _load_schema
    schema = _load_schema(schema_path)
    assert "damage_indicators" in schema
    assert "vehicle_identification" in schema
    assert "scene_conditions" in schema
    assert "forensic_flags" in schema
