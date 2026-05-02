"""Unit tests for ClaimOrchestrator — fully mocked state store and broadcaster."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)
from backend.pipeline.orchestrator import ClaimOrchestrator


def _make_store() -> tuple[MagicMock, list[dict]]:
    """Create a mock state store that tracks upserted items."""
    items: list[dict] = []

    store = MagicMock()

    # update_step returns the updated record
    def fake_update(claim_id, step, status, output=None, error=None):
        now = datetime.utcnow()
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = now
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    s.completed_at = now
                if output is not None:
                    s.output = output
                if error is not None:
                    s.error = error
        return record

    store.update_step.side_effect = fake_update

    # get_claim returns a basic record
    def fake_get(claim_id):
        return ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )

    store.get_claim.side_effect = fake_get
    store.mark_claim_status.return_value = None
    return store, items


def _make_orchestrator(use_stubs: bool = True) -> tuple[ClaimOrchestrator, MagicMock, list[dict]]:
    store, items = _make_store()
    broadcaster = MagicMock()
    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = use_stubs
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=broadcaster)
    return orch, broadcaster, items


@pytest.mark.asyncio
async def test_run_pipeline_completes_all_steps():
    orch, broadcaster, _ = _make_orchestrator(use_stubs=True)
    record = ClaimRecord(
        claim_id="test-001",
        claimant_name="John Doe",
        policy_number="AB12345678",
    )

    result = await orch.run_pipeline(record)

    # With stub extraction, the extracted fields match submitted data,
    # but policy AB12345678 is not in the demo policy index → ESCALATED
    assert result.status in (ClaimStatus.APPROVED, ClaimStatus.ESCALATED)
    assert result.classification_result is not None
    assert result.extraction_result is not None
    assert result.fraud_result is not None
    assert result.decision_result is not None
    assert result.pipeline_duration_seconds is not None


@pytest.mark.asyncio
async def test_run_pipeline_emits_signalr_events():
    orch, broadcaster, _ = _make_orchestrator(use_stubs=True)
    record = ClaimRecord(claim_id="test-002")

    await orch.run_pipeline(record)

    assert broadcaster.broadcast_step_event.call_count > 0


@pytest.mark.asyncio
async def test_run_pipeline_with_no_audio_skips_voice():
    orch, _, _ = _make_orchestrator(use_stubs=True)
    record = ClaimRecord(claim_id="test-003", audio_blob_url=None)

    result = await orch.run_pipeline(record)

    assert result.voice_transcript == {"status": "skipped", "note": "No audio provided"}


@pytest.mark.asyncio
async def test_run_pipeline_with_audio_processes_voice_stub():
    orch, _, _ = _make_orchestrator(use_stubs=True)
    record = ClaimRecord(claim_id="test-004", audio_blob_url="https://blob/audio.wav")

    result = await orch.run_pipeline(record)

    assert result.voice_transcript is not None
    assert result.voice_transcript["status"] == "stub"


@pytest.mark.asyncio
async def test_run_pipeline_failure_sets_failed_status():
    store, _ = _make_store()
    call_count = 0
    original_update = store.update_step.side_effect

    def failing_update(claim_id, step, status, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            raise RuntimeError("Simulated failure")
        return original_update(claim_id, step, status, **kwargs)

    store.update_step.side_effect = failing_update
    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = True
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=MagicMock())
    record = ClaimRecord(claim_id="test-005")

    result = await orch.run_pipeline(record)

    assert result.status == ClaimStatus.ESCALATED
    store.mark_claim_status.assert_called_with("test-005", ClaimStatus.ESCALATED)


@pytest.mark.asyncio
async def test_stub_document_ingestion_returns_stub():
    orch, _, _ = _make_orchestrator(use_stubs=True)
    result = await orch._step_ingest_document("test-010", "https://blob/form.pdf")
    assert result["status"] == "stub"
    assert result["blob_url"] == "https://blob/form.pdf"


@pytest.mark.asyncio
async def test_stub_image_ingestion_returns_stub():
    orch, _, _ = _make_orchestrator(use_stubs=True)
    result = await orch._step_ingest_images("test-011", ["https://blob/img.jpg"])
    assert result["status"] == "stub"
    assert result["image_count"] == 1


@pytest.mark.asyncio
async def test_stub_voice_ingestion_returns_stub():
    orch, _, _ = _make_orchestrator(use_stubs=True)
    result = await orch._step_ingest_voice("test-012", "https://blob/audio.wav")
    assert result["status"] == "stub"


@pytest.mark.asyncio
async def test_real_document_ingestion_calls_service():
    orch, _, _ = _make_orchestrator(use_stubs=False)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "markdown_content": "# Form",
        "fields": {"applicant_name": {"value": "Maria Thompson"}},
        "pages": 1,
    }

    with patch.object(orch, "_get_doc_intel_service") as mock_get:
        mock_service = AsyncMock()
        mock_service.extract_claim_form.return_value = mock_result
        mock_get.return_value = mock_service

        result = await orch._step_ingest_document("test-020", "https://blob/form.pdf")

    assert result["status"] == "completed"
    assert result["fields"]["applicant_name"]["value"] == "Maria Thompson"
    mock_service.extract_claim_form.assert_called_once_with("https://blob/form.pdf")


@pytest.mark.asyncio
async def test_real_document_ingestion_no_blob():
    orch, _, _ = _make_orchestrator(use_stubs=False)
    result = await orch._step_ingest_document("test-021", None)
    assert result["status"] == "completed"
    assert "No form document provided" in result["note"]


@pytest.mark.asyncio
async def test_real_document_ingestion_failure():
    orch, _, _ = _make_orchestrator(use_stubs=False)

    with patch.object(orch, "_get_doc_intel_service") as mock_get:
        mock_service = AsyncMock()
        mock_service.extract_claim_form.side_effect = RuntimeError("Azure unavailable")
        mock_get.return_value = mock_service

        result = await orch._step_ingest_document("test-022", "https://blob/form.pdf")

    assert result["status"] == "failed"
    assert "Azure unavailable" in result["error"]


@pytest.mark.asyncio
async def test_real_image_ingestion_calls_service():
    orch, _, _ = _make_orchestrator(use_stubs=False)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "damage_indicators": [{"type": "dent", "severity": "moderate"}],
        "forensic_flags": ["inconsistent_damage_angle"],
        "vehicle_identification": {},
        "scene_conditions": {},
    }

    with patch.object(orch, "_get_content_understanding_service") as mock_get:
        mock_service = AsyncMock()
        mock_service.analyze_accident_image.return_value = mock_result
        mock_get.return_value = mock_service

        result = await orch._step_ingest_images("test-023", ["https://blob/img1.jpg", "https://blob/img2.jpg"])

    assert result["status"] == "completed"
    assert result["image_count"] == 2
    assert len(result["damage_indicators"]) == 2
    assert len(result["forensic_flags"]) == 2


@pytest.mark.asyncio
async def test_real_image_ingestion_failure():
    orch, _, _ = _make_orchestrator(use_stubs=False)

    with patch.object(orch, "_get_content_understanding_service") as mock_get:
        mock_service = AsyncMock()
        mock_service.analyze_accident_image.side_effect = RuntimeError("Analyzer not found")
        mock_get.return_value = mock_service

        result = await orch._step_ingest_images("test-024", ["https://blob/img.jpg"])

    assert result["status"] == "failed"
    assert "Analyzer not found" in result["error"]


@pytest.mark.asyncio
async def test_real_voice_ingestion_calls_service():
    orch, _, _ = _make_orchestrator(use_stubs=False)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "original_text": "I was driving on the highway...",
        "detected_language": "en-US",
        "duration_seconds": 15.0,
    }

    with patch.object(orch, "_get_blob_service") as mock_blob_get, \
         patch.object(orch, "_get_speech_service") as mock_speech_get, \
         patch("os.unlink"):
        mock_blob = MagicMock()
        mock_blob.download_blob_to_temp.return_value = "/tmp/test_audio.wav"
        mock_blob_get.return_value = mock_blob

        mock_speech = AsyncMock()
        mock_speech.transcribe_voice_statement.return_value = mock_result
        mock_speech_get.return_value = mock_speech

        result = await orch._step_ingest_voice("test-025", "https://blob/audio.wav")

    assert result["status"] == "completed"
    assert result["original_text"] == "I was driving on the highway..."
    mock_speech.transcribe_voice_statement.assert_called_once_with("/tmp/test_audio.wav")


@pytest.mark.asyncio
async def test_real_voice_ingestion_failure():
    orch, _, _ = _make_orchestrator(use_stubs=False)

    with patch.object(orch, "_get_blob_service") as mock_blob_get, \
         patch("os.unlink"):
        mock_blob = MagicMock()
        mock_blob.download_blob_to_temp.return_value = "/tmp/test_audio.wav"
        mock_blob_get.return_value = mock_blob

        with patch.object(orch, "_get_speech_service") as mock_speech_get:
            mock_speech = AsyncMock()
            mock_speech.transcribe_voice_statement.side_effect = RuntimeError("STT error")
            mock_speech_get.return_value = mock_speech

            result = await orch._step_ingest_voice("test-026", "https://blob/audio.wav")

    assert result["status"] == "failed"
    assert "STT error" in result["error"]
