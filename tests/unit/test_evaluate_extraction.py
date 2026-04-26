"""Unit tests for extraction evaluation harness."""

import json
import tempfile
from pathlib import Path

from evaluation.evaluate_extraction import (
    aggregate_metrics,
    compute_metrics,
    run_evaluation,
)


def _sample_ground_truth() -> dict:
    return {
        "policy_number": "AB12345678",
        "applicant_name": "John Doe",
        "vehicle_vin": "1HGCG5655WA012345",
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_year": 2023,
        "loss_date": "2026-04-15",
        "loss_description": "Front-end collision",
        "estimated_repair_amount": 8400.00,
        "coverage_type": "COMPREHENSIVE",
        "policy_expiry_date": "2026-11-30",
    }


def _sample_extracted() -> dict:
    return {
        "policy_number": "AB12345678",
        "applicant_name": "John Doe",
        "vin": "1HGCG5655WA012345",
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_year": 2023,
        "loss_date": "2026-04-15",
        "loss_description": "Front-end collision",
        "estimated_repair_amount": 8400.00,
        "coverage_type": "COMPREHENSIVE",
        "policy_expiry": "2026-11-30",
    }


def test_compute_metrics_perfect():
    gt = _sample_ground_truth()
    ext = _sample_extracted()
    metrics = compute_metrics(ext, gt)

    for field, m in metrics.items():
        assert m["f1"] == 1.0, f"Field {field} should be perfect"


def test_compute_metrics_missing_field():
    gt = _sample_ground_truth()
    ext = _sample_extracted()
    ext["vin"] = None

    metrics = compute_metrics(ext, gt)
    assert metrics["vin"]["recall"] == 0.0
    assert metrics["vin"]["f1"] == 0.0


def test_compute_metrics_wrong_value():
    gt = _sample_ground_truth()
    ext = _sample_extracted()
    ext["vehicle_make"] = "Honda"

    metrics = compute_metrics(ext, gt)
    assert metrics["vehicle_make"]["f1"] == 0.0


def test_aggregate_metrics():
    gt = _sample_ground_truth()
    ext = _sample_extracted()
    ext["vin"] = None

    results = [compute_metrics(ext, gt)]
    aggregated = aggregate_metrics(results)
    assert aggregated["vin"]["f1"] == 0.0
    assert aggregated["policy_number"]["f1"] == 1.0


def test_run_evaluation_with_temp_dir():
    gt = _sample_ground_truth()

    with tempfile.TemporaryDirectory() as tmpdir:
        label_path = Path(tmpdir) / "acord_0001.json"
        label_path.write_text(json.dumps(gt))

        result = run_evaluation(labels_dir=Path(tmpdir), mode="mocked")

        assert result["sample_count"] == 1
        assert result["overall_f1"] >= 0.90


def test_run_evaluation_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_evaluation(labels_dir=Path(tmpdir), mode="mocked")
        assert result["sample_count"] == 0
        assert result["overall_f1"] == 0.0
