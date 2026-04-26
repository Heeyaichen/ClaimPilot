"""Unit tests for the ACORD synthetic dataset generator."""

from __future__ import annotations

import json
import random
import re
import tempfile
from pathlib import Path

from evaluation.generate_acord_synthetic import (
    _rand_policy_number,
    _rand_vin,
    generate_form_data,
    main,
)

# ---------------------------------------------------------------------------
# test_deterministic_generation_with_seed
# ---------------------------------------------------------------------------


class TestDeterministicGeneration:
    """Verify that the same seed always produces identical output."""

    def test_deterministic_generation_with_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Generate twice with the same seed
            result_a = main(count=5, training_count=3, seed=42, base_dir=base / "run_a")
            result_b = main(count=5, training_count=3, seed=42, base_dir=base / "run_b")

            # Same summary
            assert result_a["total_forms"] == result_b["total_forms"]
            assert result_a["training_samples"] == result_b["training_samples"]

            # Compare every ground-truth JSON
            for i in range(1, 6):
                prefix = f"acord_{i:04d}"
                json_a = json.loads((base / "run_a" / "labels" / f"{prefix}.json").read_text())
                json_b = json.loads((base / "run_b" / "labels" / f"{prefix}.json").read_text())
                assert json_a == json_b, f"Form {prefix} differs between runs"

            # Compare PDFs byte-for-byte
            for i in range(1, 6):
                prefix = f"acord_{i:04d}"
                pdf_a = (base / "run_a" / "forms" / f"{prefix}.pdf").read_bytes()
                pdf_b = (base / "run_b" / "forms" / f"{prefix}.pdf").read_bytes()
                assert pdf_a == pdf_b, f"PDF {prefix} differs between runs"


# ---------------------------------------------------------------------------
# test_ground_truth_matches_form_count
# ---------------------------------------------------------------------------


class TestGroundTruthMatch:
    """Ground-truth JSON files must be 1:1 with PDF forms."""

    def test_ground_truth_matches_form_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            count = 7
            result = main(count=count, training_count=3, seed=99, base_dir=Path(tmpdir))

            assert result["total_forms"] == count

            forms = list((Path(tmpdir) / "forms").glob("*.pdf"))
            labels = list((Path(tmpdir) / "labels").glob("*.json"))

            assert len(forms) == count
            assert len(labels) == count

            # Every PDF has a matching JSON
            form_stems = {p.stem for p in forms}
            label_stems = {p.stem for p in labels}
            assert form_stems == label_stems


# ---------------------------------------------------------------------------
# test_training_samples_created
# ---------------------------------------------------------------------------


class TestTrainingSamples:
    """Verify Azure DI training samples are properly created."""

    def test_training_samples_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            training_count = 5
            result = main(count=10, training_count=training_count, seed=7, base_dir=Path(tmpdir))

            assert result["training_samples"] == training_count

            training_dir = Path(tmpdir) / "training"
            sample_dirs = [d for d in training_dir.iterdir() if d.is_dir()]
            assert len(sample_dirs) == training_count

            for sample_dir in sorted(sample_dirs):
                # Each sample dir must contain: PDF, ocr.json, labels.json
                pdfs = list(sample_dir.glob("*.pdf"))
                assert len(pdfs) == 1, f"Expected 1 PDF in {sample_dir}, found {len(pdfs)}"

                assert (sample_dir / "ocr.json").exists(), f"Missing ocr.json in {sample_dir}"
                assert (sample_dir / "labels.json").exists(), f"Missing labels.json in {sample_dir}"

                # Validate JSON structure
                ocr = json.loads((sample_dir / "ocr.json").read_text())
                assert "analyzeResult" in ocr
                assert "pages" in ocr["analyzeResult"]
                assert len(ocr["analyzeResult"]["pages"]) >= 1

                labels = json.loads((sample_dir / "labels.json").read_text())
                assert "document" in labels
                assert "labels" in labels
                assert isinstance(labels["labels"], list)
                assert len(labels["labels"]) > 0

    def test_training_count_capped_at_total(self) -> None:
        """If training_count > count, it should be capped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = main(count=5, training_count=100, seed=1, base_dir=Path(tmpdir))
            assert result["training_samples"] == 5


# ---------------------------------------------------------------------------
# test_policy_number_format
# ---------------------------------------------------------------------------


class TestPolicyNumberFormat:
    """Policy numbers must be 2 uppercase letters + 8 digits."""

    _PATTERN = re.compile(r"^[A-Z]{2}\d{8}$")

    def test_policy_number_format(self) -> None:
        rng = random.Random(42)
        for _ in range(200):
            pn = _rand_policy_number(rng)
            assert self._PATTERN.match(pn), f"Policy number '{pn}' does not match format"

    def test_policy_number_in_generated_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            main(count=20, training_count=0, seed=55, base_dir=Path(tmpdir))
            labels_dir = Path(tmpdir) / "labels"
            for label_file in sorted(labels_dir.glob("*.json")):
                data = json.loads(label_file.read_text())
                pn = data["policy_number"]
                assert self._PATTERN.match(pn), f"Invalid policy number '{pn}' in {label_file.name}"


# ---------------------------------------------------------------------------
# test_vin_format
# ---------------------------------------------------------------------------


class TestVinFormat:
    """VINs must be exactly 17 characters, alphanumeric, no I/O/Q."""

    _PATTERN = re.compile(r"^[0-9A-HJ-NPR-Z]{17}$")

    def test_vin_format(self) -> None:
        rng = random.Random(42)
        for _ in range(200):
            vin = _rand_vin(rng)
            assert len(vin) == 17, f"VIN '{vin}' is not 17 characters"
            assert self._PATTERN.match(vin), f"VIN '{vin}' contains invalid characters"
            # Ensure no I, O, Q
            assert "I" not in vin
            assert "O" not in vin
            assert "Q" not in vin

    def test_vin_in_generated_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            main(count=20, training_count=0, seed=77, base_dir=Path(tmpdir))
            labels_dir = Path(tmpdir) / "labels"
            for label_file in sorted(labels_dir.glob("*.json")):
                data = json.loads(label_file.read_text())
                vin = data["vehicle_vin"]
                assert len(vin) == 17, f"VIN '{vin}' in {label_file.name} is not 17 chars"
                assert self._PATTERN.match(vin), f"VIN '{vin}' in {label_file.name} invalid"


# ---------------------------------------------------------------------------
# Additional sanity checks
# ---------------------------------------------------------------------------


class TestFormGenerationSanity:
    """Quick sanity checks on generated form data."""

    def test_vehicle_year_range(self) -> None:
        rng = random.Random(42)
        for _ in range(100):
            data = generate_form_data(rng)
            assert 2015 <= data.vehicle_year <= 2026

    def test_repair_amount_range(self) -> None:
        rng = random.Random(42)
        for _ in range(100):
            data = generate_form_data(rng)
            assert 500 <= data.estimated_repair_amount <= 25000

    def test_pdf_is_valid(self) -> None:
        """Generated PDF starts with the PDF magic bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            main(count=1, training_count=0, seed=10, base_dir=Path(tmpdir))
            pdf_path = Path(tmpdir) / "forms" / "acord_0001.pdf"
            content = pdf_path.read_bytes()
            assert content[:5] == b"%PDF-"
