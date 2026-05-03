"""GPT-4o Vision-based image analysis fallback for accident damage photos.

Uses the Azure OpenAI chat completions API with image input to analyze
vehicle damage photos when Content Understanding is unavailable.
Outputs the same ImageAnalysisResult schema as ContentUnderstandingService.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from backend.core.config import get_settings
from backend.models.ingestion import (
    DamageIndicator,
    ImageAnalysisResult,
    SceneConditions,
    VehicleIdentification,
)

logger = logging.getLogger(__name__)

VISION_SYSTEM_PROMPT = """You are a vehicle damage analyst for an insurance claims system.
Analyze the provided accident photo and return a JSON object with this exact structure:

{
  "damage_indicators": [
    {"panel": "front|rear|driver_side|passenger_side|roof|undercarriage",
     "severity": "minor|moderate|severe|total_loss_candidate",
     "description": "brief description"}
  ],
  "vehicle_identification": {
    "make": "", "model": "", "year": null, "color": "",
    "license_plate_visible": false, "license_plate_value": null
  },
  "scene_conditions": {
    "time_of_day_estimated": "", "weather_conditions": "", "location_type": ""
  },
  "forensic_flags": []
}

Forensic flags indicate suspicious elements: inconsistent damage, signs of staging, etc.
Return ONLY valid JSON. Use empty arrays/strings if not observable."""


class FoundryVisionService:
    """Analyze accident images using GPT-4o vision capabilities."""

    def __init__(self) -> None:
        settings = get_settings()
        self._endpoint = settings.azure_foundry_project_endpoint
        self._model_deployment = settings.foundry_model_deployment

    def _get_openai_client(self):
        """Create an AzureOpenAI client."""
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        endpoint = self._endpoint
        if "/projects/" in endpoint:
            endpoint = endpoint.split("/projects/")[0]
        if endpoint.endswith("/api"):
            endpoint = endpoint[:-4]
        if not endpoint.endswith("/"):
            endpoint += "/"

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2025-04-01-preview",
        )

    async def analyze_accident_image(self, image_url: str) -> ImageAnalysisResult:
        """Analyze an accident image using GPT-4o vision.

        Args:
            image_url: URL to the accident image (JPEG/PNG).

        Returns:
            ImageAnalysisResult with damage indicators, vehicle identification,
            scene conditions, and forensic flags.
        """
        import asyncio

        logger.info("Analyzing accident image via GPT-4o vision: %s", image_url)
        client = self._get_openai_client()

        def _call() -> ImageAnalysisResult:
            response = client.chat.completions.create(
                model=self._model_deployment,
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            },
                            {
                                "type": "text",
                                "text": "Analyze this vehicle damage photo for insurance claim processing.",
                            },
                        ],
                    },
                ],
                max_tokens=2000,
                temperature=0.1,
            )

            raw_text = response.choices[0].message.content or ""

            # Extract JSON from response
            json_str = raw_text.strip()
            match = re.search(r"(\{.*\})", json_str, re.DOTALL)
            if match:
                json_str = match.group(1)

            data = json.loads(json_str)

            damage_indicators = [
                DamageIndicator(**d) for d in data.get("damage_indicators", [])
            ]
            vehicle_identification = VehicleIdentification(
                **data.get("vehicle_identification", {})
            )
            scene_conditions = SceneConditions(**data.get("scene_conditions", {}))
            forensic_flags = data.get("forensic_flags", [])

            return ImageAnalysisResult(
                damage_indicators=damage_indicators,
                vehicle_identification=vehicle_identification,
                scene_conditions=scene_conditions,
                forensic_flags=forensic_flags,
                raw_response={"source": "foundry_vision", "data": data},
                analyzed_at=datetime.utcnow(),
            )

        return await asyncio.to_thread(_call)
