"""CLI smoke script for Azure Translator text translation.

Usage:
    python scripts/translate_text.py <text> <source_language>

Requires AZURE_TRANSLATOR_ENDPOINT and AZURE_TRANSLATOR_REGION to be set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.core.config import get_settings
from backend.services.translator import TranslatorService


async def main(text: str, source_language: str) -> None:
    settings = get_settings()
    if not settings.azure_translator_endpoint:
        print("Error: AZURE_TRANSLATOR_ENDPOINT is not configured.", file=sys.stderr)
        sys.exit(1)

    service = TranslatorService()
    result = await service.translate_to_english(text, source_language)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Translate text to English via Azure Translator")
    parser.add_argument("text", help="Text to translate")
    parser.add_argument("source_language", help="BCP-47 language tag (e.g., es-ES, fr-FR)")
    args = parser.parse_args()
    asyncio.run(main(args.text, args.source_language))
