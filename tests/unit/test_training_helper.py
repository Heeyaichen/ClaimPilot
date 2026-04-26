"""Unit tests for the Document Intelligence training helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.train_doc_intelligence_acord1 import (
    MIN_REQUIRED_SAMPLES,
    validate_training_dir,
)


class TestValidateTrainingDir:
    def test_valid_dir_with_enough_samples(self, tmp_path: Path) -> None:
        for i in range(5):
            (tmp_path / f"sample_{i:03d}").mkdir()
            (tmp_path / f"sample_{i:03d}" / "form.pdf").write_bytes(b"%PDF-fake")
        dirs = validate_training_dir(tmp_path, min_samples=5)
        assert len(dirs) == 5

    def test_dir_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Training directory not found"):
            validate_training_dir(Path("/nonexistent/path"), min_samples=1)

    def test_insufficient_samples(self, tmp_path: Path) -> None:
        for i in range(3):
            (tmp_path / f"sample_{i:03d}").mkdir()
            (tmp_path / f"sample_{i:03d}" / "form.pdf").write_bytes(b"%PDF-fake")

        with pytest.raises(ValueError, match="at least 5"):
            validate_training_dir(tmp_path, min_samples=5)

    def test_ignores_non_pdf_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "empty_dir").mkdir()
        (tmp_path / "has_pdf").mkdir()
        (tmp_path / "has_pdf" / "form.pdf").write_bytes(b"%PDF-fake")

        dirs = validate_training_dir(tmp_path, min_samples=1)
        assert len(dirs) == 1
        assert dirs[0].name == "has_pdf"

    def test_default_min_samples(self, tmp_path: Path) -> None:
        assert MIN_REQUIRED_SAMPLES == 5
