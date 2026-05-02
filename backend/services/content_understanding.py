"""Azure AI Content Understanding service wrapper for accident image analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential

from backend.core.config import get_settings
from backend.models.ingestion import (
    DamageIndicator,
    ImageAnalysisResult,
    SceneConditions,
    VehicleIdentification,
)

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "domains" / "auto_damage" / "extraction_schema.json"


class AnalyzerNotFoundError(Exception):
    """Raised when the Content Understanding analyzer does not exist (404)."""


def _load_schema(path: Path | None = None) -> dict[str, Any]:
    """Load the image analysis schema from JSON."""
    schema_file = path or _SCHEMA_PATH
    return dict(json.loads(schema_file.read_text(encoding="utf-8")))


class ContentUnderstandingService:
    """Async wrapper around Azure Content Understanding REST API for image analysis."""

    def __init__(
        self,
        endpoint: str | None = None,
        schema_path: Path | None = None,
        credential: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = (endpoint or settings.azure_content_understanding_endpoint).rstrip("/")
        self._schema = _load_schema(schema_path)
        self._credential = credential or DefaultAzureCredential()
        self._analyzer_name = settings.azure_content_understanding_analyzer_id

    async def _get_token(self) -> str:
        """Acquire an access token for Cognitive Services."""
        token = self._credential.get_token("https://cognitiveservices.azure.com/.default")
        if hasattr(token, "__await__"):
            token = await token  # type: ignore[misc]
        return str(token.token)

    async def analyze_accident_image(self, image_url: str) -> ImageAnalysisResult:
        """Analyze an accident image using Content Understanding.

        Args:
            image_url: URL to the accident image (JPEG/PNG).

        Returns:
            ImageAnalysisResult with damage indicators, vehicle identification,
            scene conditions, and forensic flags.

        Raises:
            httpx.HTTPStatusError: On HTTP errors from the service.
            ValueError: On malformed response.
        """
        logger.info("Analyzing accident image: %s", image_url)
        token = await self._get_token()

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._endpoint}/contentunderstanding/analyzers/{self._analyzer_name}/analyze",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "inputs": [{"type": "image_url", "url": image_url}],
                    "output_schema": self._schema,
                },
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise AnalyzerNotFoundError(
                    f"Analyzer '{self._analyzer_name}' not found. "
                    "Create it in the Content Understanding resource first."
                ) from exc
            raise

        data = response.json()
        result_data = data.get("result", data)

        damage_indicators = [
            DamageIndicator(**d) for d in result_data.get("damage_indicators", [])
        ]
        vehicle_identification = VehicleIdentification(
            **result_data.get("vehicle_identification", {})
        )
        scene_conditions = SceneConditions(**result_data.get("scene_conditions", {}))
        forensic_flags = result_data.get("forensic_flags", [])

        return ImageAnalysisResult(
            damage_indicators=damage_indicators,
            vehicle_identification=vehicle_identification,
            scene_conditions=scene_conditions,
            forensic_flags=forensic_flags,
            raw_response=data,
            analyzed_at=datetime.utcnow(),
        )
