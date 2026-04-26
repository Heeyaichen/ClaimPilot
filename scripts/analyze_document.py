"""CLI smoke script for Document Intelligence claim form extraction.

Usage:
    python scripts/analyze_document.py <blob_url>

Requires AZURE_DOC_INTELLIGENCE_ENDPOINT to be set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from backend.core.config import get_settings
from backend.services.document_intelligence import DocumentIntelligenceService


async def main(blob_url: str) -> None:
    settings = get_settings()
    if not settings.azure_doc_intelligence_endpoint:
        print("Error: AZURE_DOC_INTELLIGENCE_ENDPOINT is not configured.", file=sys.stderr)
        print("Set it in .env or as an environment variable.", file=sys.stderr)
        sys.exit(1)

    service = DocumentIntelligenceService()
    result = await service.extract_claim_form(blob_url)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract fields from a claim form via Document Intelligence")
    parser.add_argument("blob_url", help="URL to the claim form in Azure Blob Storage")
    args = parser.parse_args()
    asyncio.run(main(args.blob_url))
