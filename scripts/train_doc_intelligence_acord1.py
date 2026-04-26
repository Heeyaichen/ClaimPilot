"""Training helper for Azure Document Intelligence ACORD 1 custom model.

Usage:
    python scripts/train_doc_intelligence_acord1.py [--training-dir PATH] [--min-samples N]

Requires AZURE_DOC_INTELLIGENCE_ENDPOINT to be set.

The training directory should contain labeled samples in Azure Document Intelligence
training format (one subfolder per sample with the PDF and labels.json).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from backend.core.config import get_settings

MIN_REQUIRED_SAMPLES = 5
DEFAULT_TRAINING_DIR = (
    Path(__file__).resolve().parent.parent / "evaluation" / "datasets" / "acord_synthetic" / "training"
)


def validate_training_dir(training_dir: Path, min_samples: int) -> list[Path]:
    """Validate that the training directory has sufficient labeled samples.

    Returns:
        List of sample subdirectory paths.

    Raises:
        FileNotFoundError: If the training directory doesn't exist.
        ValueError: If fewer than min_samples labeled samples are found.
    """
    if not training_dir.exists():
        raise FileNotFoundError(f"Training directory not found: {training_dir}")

    sample_dirs = sorted(
        p for p in training_dir.iterdir()
        if p.is_dir() and any(p.glob("*.pdf"))
    )

    if len(sample_dirs) < min_samples:
        raise ValueError(
            f"Training requires at least {min_samples} labeled samples, "
            f"but only {len(sample_dirs)} found in {training_dir}. "
            f"Generate more with: python evaluation/generate_acord_synthetic.py --training-count {min_samples}"
        )

    return sample_dirs


async def train_model(training_dir: Path, min_samples: int) -> dict:
    """Start ACORD 1 custom model training.

    Returns:
        Dict with model_id and training status.

    Raises:
        ValueError: If insufficient training samples.
        FileNotFoundError: If training directory missing.
    """
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.identity import DefaultAzureCredential

    settings = get_settings()
    if not settings.azure_doc_intelligence_endpoint:
        raise ValueError("AZURE_DOC_INTELLIGENCE_ENDPOINT is not configured")

    validate_training_dir(training_dir, min_samples)

    credential = DefaultAzureCredential()
    client = DocumentIntelligenceClient(
        endpoint=settings.azure_doc_intelligence_endpoint,
        credential=credential,
    )

    # Build the training data source URL or use the training container SAS.
    # For Phase 1, we construct a container URL from the training directory.
    # In production, this would be a blob container SAS URL.
    container_url = os.environ.get("TRAINING_CONTAINER_SAS_URL", "")
    if not container_url:
        raise ValueError(
            "TRAINING_CONTAINER_SAS_URL environment variable must be set "
            "to a SAS URL for the blob container containing training data. "
            "Upload the training/ directory to a blob container and generate a SAS URL."
        )

    poller = client.begin_build_model(
        build_request={
            "model_id": "acord-1-custom",
            "description": "ACORD 1 Personal Auto Application custom model",
            "azure_blob_source": {"container_url": container_url},
            "build_mode": "template",
        },
    )

    model = poller.result()

    return {
        "model_id": model.model_id,
        "description": model.description,
        "status": model.status,
        "created_at": str(model.created_date_time) if model.created_date_time else None,
        "api_version": model.api_version,
        "doc_types": list(model.doc_types.keys()) if model.doc_types else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Document Intelligence ACORD 1 model")
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=DEFAULT_TRAINING_DIR,
        help=f"Path to training data directory (default: {DEFAULT_TRAINING_DIR})",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=MIN_REQUIRED_SAMPLES,
        help=f"Minimum number of labeled samples required (default: {MIN_REQUIRED_SAMPLES})",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the training directory without starting training",
    )
    args = parser.parse_args()

    try:
        sample_dirs = validate_training_dir(args.training_dir, args.min_samples)
        print(json.dumps({
            "status": "valid",
            "training_dir": str(args.training_dir),
            "sample_count": len(sample_dirs),
            "samples": [d.name for d in sample_dirs],
        }, indent=2))

        if args.validate_only:
            return

    except (FileNotFoundError, ValueError) as e:
        print(json.dumps({"status": "error", "message": str(e)}, indent=2))
        sys.exit(1)

    import asyncio
    try:
        result = asyncio.run(train_model(args.training_dir, args.min_samples))
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
