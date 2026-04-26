"""CLI smoke script for Content Understanding image analysis.

Usage:
    python scripts/analyze_image.py <image_url>

Requires AZURE_CONTENT_UNDERSTANDING_ENDPOINT to be set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.core.config import get_settings
from backend.services.content_understanding import ContentUnderstandingService


async def main(image_url: str) -> None:
    settings = get_settings()
    if not settings.azure_content_understanding_endpoint:
        print("Error: AZURE_CONTENT_UNDERSTANDING_ENDPOINT is not configured.", file=sys.stderr)
        sys.exit(1)

    service = ContentUnderstandingService()
    result = await service.analyze_accident_image(image_url)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze an accident image via Content Understanding")
    parser.add_argument("image_url", help="URL to the accident image")
    args = parser.parse_args()
    asyncio.run(main(args.image_url))
