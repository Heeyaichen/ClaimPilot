"""Unit tests for the demo asset generator (scripts/generate_demo_assets.py)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts.generate_demo_assets import SCENARIOS, generate_demo_assets

# ---------------------------------------------------------------------------
# Expected constants
# ---------------------------------------------------------------------------

VALID_OUTCOMES = {"APPROVED", "ESCALATED", "FRAUD_REVIEW"}
EXPECTED_FOLDERS = {"claim_001_approve", "claim_002_escalate", "claim_003_fraud_review"}
REQUIRED_FILES = {"metadata.json", "claim_form.pdf", "voice_statement.txt"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGeneratorRuns:
    """The generator must complete without errors."""

    def test_generate_to_temp_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_demo_assets(output_dir=Path(tmpdir))
            assert result["total_claims"] == 3
            assert set(result["bundles"]) == EXPECTED_FOLDERS

    def test_output_dir_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "output"
            generate_demo_assets(output_dir=out)
            assert out.is_dir()


class TestMetadataSchema:
    """metadata.json must have required fields with correct types/values."""

    def test_required_fields_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                meta = json.loads((Path(tmpdir) / folder / "metadata.json").read_text())
                for field in ("claimant_name", "policy_number", "scenario", "expected_outcome", "files"):
                    assert field in meta, f"Missing field '{field}' in {folder}/metadata.json"

    def test_expected_outcome_enum(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                meta = json.loads((Path(tmpdir) / folder / "metadata.json").read_text())
                assert meta["expected_outcome"] in VALID_OUTCOMES

    def test_files_section_has_required_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                meta = json.loads((Path(tmpdir) / folder / "metadata.json").read_text())
                files = meta["files"]
                assert "claim_form" in files
                assert "photos" in files
                assert "voice_transcript" in files
                assert isinstance(files["photos"], list)
                assert len(files["photos"]) >= 1


class TestFilePresence:
    """Each claim folder must contain the expected files."""

    def test_all_required_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                claim_dir = Path(tmpdir) / folder
                for fname in REQUIRED_FILES:
                    assert (claim_dir / fname).exists(), f"Missing {fname} in {folder}"

    def test_at_least_one_jpg_per_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                claim_dir = Path(tmpdir) / folder
                jpgs = list(claim_dir.glob("*.jpg"))
                assert len(jpgs) >= 1, f"No JPG images in {folder}"

    def test_pdf_is_valid(self) -> None:
        """Generated PDFs start with PDF magic bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                pdf_path = Path(tmpdir) / folder / "claim_form.pdf"
                content = pdf_path.read_bytes()
                assert content[:5] == b"%PDF-"


class TestMetadataConsistency:
    """metadata.json values must match the generated PDF data."""

    def test_claimant_name_matches_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for scenario in SCENARIOS:
                meta = json.loads(
                    (Path(tmpdir) / scenario["folder"] / "metadata.json").read_text()
                )
                expected_name = scenario["form_data"].claimant_name
                assert meta["claimant_name"] == expected_name

    def test_policy_number_matches_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for scenario in SCENARIOS:
                meta = json.loads(
                    (Path(tmpdir) / scenario["folder"] / "metadata.json").read_text()
                )
                expected_pn = scenario["form_data"].policy_number
                assert meta["policy_number"] == expected_pn

    def test_photo_filenames_match_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_demo_assets(output_dir=Path(tmpdir))
            for folder in EXPECTED_FOLDERS:
                claim_dir = Path(tmpdir) / folder
                meta = json.loads((claim_dir / "metadata.json").read_text())
                for photo_name in meta["files"]["photos"]:
                    assert (claim_dir / photo_name).exists(), f"Listed photo {photo_name} missing in {folder}"
