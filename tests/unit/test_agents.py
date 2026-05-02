"""Unit tests for agent stub outputs and pipeline wiring."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.base import AgentResponseError, FoundryAgentClient
from backend.agents.classifier_agent import ClassifierAgent
from backend.agents.decision_agent import DecisionAgent
from backend.agents.extractor_agent import ExtractorAgent
from backend.agents.fraud_agent import FraudDetectionAgent
from backend.models.claim import (
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)


def _make_orchestrator():
    """Create an orchestrator with mock store and broadcaster."""
    from backend.pipeline.orchestrator import ClaimOrchestrator

    store = MagicMock()

    def fake_update(claim_id, step, status, output=None, error=None):
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = datetime.utcnow()
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    s.completed_at = datetime.utcnow()
                if output is not None:
                    s.output = output
        return record

    store.update_step.side_effect = fake_update

    def fake_get(claim_id):
        return ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )

    store.get_claim.side_effect = fake_get
    store.mark_claim_status.return_value = None

    broadcaster = MagicMock()
    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = True
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=broadcaster)
    return orch, broadcaster


# --- Agent stub outputs ---


def test_classifier_stub():
    result = ClassifierAgent._stub_classify(None)
    assert result.claim_type == "AUTO_PHYSICAL_DAMAGE"
    assert result.confidence > 0
    assert not result.requires_human_review


def test_extractor_stub():
    result = ExtractorAgent._stub_extract()
    assert result.policy_number is not None
    assert result.fields_extracted == 12
    assert result.confidence > 0


def test_fraud_stub():
    result = FraudDetectionAgent._stub_assess()
    assert result.score < 0.4
    assert result.recommendation == "proceed"


def test_decision_stub():
    result = DecisionAgent._stub_decide()
    assert result.decision == "APPROVE"
    assert result.approved_amount is not None
    assert len(result.reasoning_chain) > 0
    # All reasoning steps must have evidence sources
    for step in result.reasoning_chain:
        assert step.evidence_source != "stub"
        assert step.evidence_value is not None


# --- Pipeline wiring with stubs ---


@pytest.mark.asyncio
async def test_pipeline_runs_all_8_steps():
    orch, broadcaster = _make_orchestrator()
    record = ClaimRecord(
        claim_id="test-p3-001",
        claimant_name="John Doe",
        policy_number="AB12345678",
    )

    result = await orch.run_pipeline(record)
    # Stub policy AB12345678 is not in demo index → ESCALATED
    assert result.status in (ClaimStatus.APPROVED, ClaimStatus.ESCALATED)
    assert result.classification_result is not None
    assert result.extraction_result is not None
    assert result.fraud_result is not None
    assert result.decision_result is not None
    assert result.pipeline_duration_seconds is not None


@pytest.mark.asyncio
async def test_pipeline_classify_uses_agent():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-002", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    assert result.classification_result["claim_type"] == "AUTO_PHYSICAL_DAMAGE"


@pytest.mark.asyncio
async def test_pipeline_decision_has_reasoning_chain():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-003", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    chain = result.decision_result["reasoning_chain"]
    assert len(chain) >= 1
    for step in chain:
        assert "evidence_source" in step
        assert "evidence_value" in step


@pytest.mark.asyncio
async def test_pipeline_fraud_result_has_recommendation():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-004", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    assert result.fraud_result["recommendation"] in (
        "proceed",
        "adjuster_review",
        "escalate_siu",
    )


@pytest.mark.asyncio
async def test_pipeline_emits_signalr_events():
    orch, broadcaster = _make_orchestrator()
    record = ClaimRecord(claim_id="test-p3-005", claimant_name="John Doe", policy_number="AB12345678")
    await orch.run_pipeline(record)
    assert broadcaster.broadcast_step_event.call_count > 0


@pytest.mark.asyncio
async def test_pipeline_voice_skip():
    orch, _ = _make_orchestrator()
    record = ClaimRecord(
        claim_id="test-p3-006",
        audio_blob_url=None,
        claimant_name="John Doe",
        policy_number="AB12345678",
    )
    result = await orch.run_pipeline(record)
    assert result.voice_transcript["status"] == "skipped"


@pytest.mark.asyncio
async def test_pipeline_failure_sets_failed():
    store = MagicMock()
    call_count = 0

    def failing_update(claim_id, step, status, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 3:
            raise RuntimeError("Simulated failure")
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = datetime.utcnow()
                if status in (StepStatus.COMPLETED, StepStatus.FAILED):
                    s.completed_at = datetime.utcnow()
        return record

    store.update_step.side_effect = failing_update
    store.get_claim.side_effect = lambda cid: ClaimRecord(
        claim_id=cid, steps=[PipelineStepState(step=s) for s in PipelineStep]
    )

    from backend.pipeline.orchestrator import ClaimOrchestrator

    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = True
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=MagicMock())
    record = ClaimRecord(claim_id="test-p3-007", claimant_name="John Doe", policy_number="AB12345678")
    result = await orch.run_pipeline(record)
    assert result.status == ClaimStatus.FAILED


# --- Rate-limit retry and live-mode agent error handling ---


class TestRateLimitRetry:
    """Tests for rate-limit retry logic in FoundryAgentClient._call_foundry."""

    def _make_client(self) -> FoundryAgentClient:
        """Create a FoundryAgentClient in live mode with mocked settings."""
        with patch("backend.agents.base.get_settings") as mock_settings:
            settings = MagicMock()
            settings.azure_foundry_project_endpoint = "https://test.cognitiveservices.azure.com/"
            settings.foundry_model_deployment = "gpt-4o"
            settings.use_stub_agents = False
            mock_settings.return_value = settings
            return FoundryAgentClient(agent_id="asst_test123")

    def test_rate_limit_retry_succeeds(self):
        """Rate limit on first attempt, success on retry."""
        client = self._make_client()

        mock_openai_client = MagicMock()
        mock_thread = MagicMock()
        mock_thread.id = "thread_123"
        mock_run = MagicMock()
        mock_run.status = "completed"
        mock_msg = MagicMock()
        mock_msg.role = "assistant"
        mock_msg.content = [MagicMock()]
        mock_msg.content[0].text.value = (
            '{"claim_type": "AUTO_PHYSICAL_DAMAGE", '
            '"confidence": 0.9, "routing_rationale": "test", '
            '"requires_human_review": false}'
        )

        mock_openai_client.beta.threads.create.return_value = mock_thread
        mock_openai_client.beta.threads.messages.create.return_value = None
        mock_openai_client.beta.threads.messages.list.return_value = MagicMock(
            data=[mock_msg]
        )

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from openai import RateLimitError
                resp = MagicMock()
                resp.status_code = 429
                raise RateLimitError(
                    message="Rate limit exceeded",
                    response=resp,
                    body=None,
                )
            return mock_run

        mock_openai_client.beta.threads.runs.create_and_poll.side_effect = side_effect

        with patch.object(client, "_get_openai_client", return_value=mock_openai_client):
            with patch("backend.agents.base.time.sleep"):
                result = client._call_foundry("system", "user")

        assert "AUTO_PHYSICAL_DAMAGE" in result
        assert call_count == 2

    def test_rate_limit_exhausted_raises(self):
        """After MAX_RATE_LIMIT_RETRIES+1 attempts, raise AgentResponseError."""
        client = self._make_client()

        mock_openai_client = MagicMock()
        mock_thread = MagicMock()
        mock_thread.id = "thread_123"
        mock_openai_client.beta.threads.create.return_value = mock_thread
        mock_openai_client.beta.threads.messages.create.return_value = None

        from openai import RateLimitError

        resp = MagicMock()
        resp.status_code = 429

        mock_openai_client.beta.threads.runs.create_and_poll.side_effect = (
            RateLimitError(message="Rate limit exceeded", response=resp, body=None)
        )

        with patch.object(client, "_get_openai_client", return_value=mock_openai_client):
            with patch("backend.agents.base.time.sleep"):
                with pytest.raises(AgentResponseError, match="rate limit"):
                    client._call_foundry("system", "user")


class TestLiveModeNoStubFallback:
    """Tests that agents don't silently fall back to stubs in live mode."""

    def _make_agent_in_live_mode(self, agent_cls):
        """Create an agent in live mode with a mock client that raises."""
        mock_client = MagicMock(spec=FoundryAgentClient)
        mock_client.run_agent.side_effect = AgentResponseError("API error")

        with patch("backend.core.config.get_settings") as mock_settings:
            settings = MagicMock()
            settings.use_stub_agents = False
            settings.classifier_agent_id = "asst_test"
            settings.extractor_agent_id = "asst_test"
            settings.fraud_agent_id = "asst_test"
            settings.decision_agent_id = "asst_test"
            mock_settings.return_value = settings
            return agent_cls(client=mock_client)

    def test_classifier_raises_in_live_mode(self):
        agent = self._make_agent_in_live_mode(ClassifierAgent)
        with pytest.raises(AgentResponseError):
            agent.classify()

    def test_extractor_raises_in_live_mode(self):
        agent = self._make_agent_in_live_mode(ExtractorAgent)
        with pytest.raises(AgentResponseError):
            agent.extract()

    def test_fraud_raises_in_live_mode(self):
        agent = self._make_agent_in_live_mode(FraudDetectionAgent)
        with pytest.raises(AgentResponseError):
            agent.assess()

    def test_decision_raises_in_live_mode(self):
        agent = self._make_agent_in_live_mode(DecisionAgent)
        with pytest.raises(AgentResponseError):
            agent.decide()


@pytest.mark.asyncio
async def test_pipeline_agent_error_sets_escalated():
    """AgentResponseError from agent calls should ESCALATE, not FAIL."""
    store = MagicMock()

    def fake_update(claim_id, step, status, output=None, error=None):
        record = ClaimRecord(
            claim_id=claim_id,
            steps=[PipelineStepState(step=s) for s in PipelineStep],
        )
        for s in record.steps:
            if s.step == step:
                s.status = status
                if status == StepStatus.RUNNING:
                    s.started_at = datetime.utcnow()
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    s.completed_at = datetime.utcnow()
        return record

    store.update_step.side_effect = fake_update
    store.get_claim.side_effect = lambda cid: ClaimRecord(
        claim_id=cid, steps=[PipelineStepState(step=s) for s in PipelineStep]
    )
    store.mark_claim_status.return_value = None

    from backend.pipeline.orchestrator import ClaimOrchestrator

    with patch("backend.pipeline.orchestrator.get_settings") as mock_settings:
        settings = MagicMock()
        settings.use_stub_agents = False
        mock_settings.return_value = settings
        orch = ClaimOrchestrator(state_store=store, broadcaster=MagicMock())

    # Make run_classification raise AgentResponseError
    with patch(
        "backend.pipeline.orchestrator.run_classification",
        side_effect=AgentResponseError("Agent unavailable due to rate limit"),
    ):
        record = ClaimRecord(
            claim_id="test-rl-001",
            claimant_name="Test",
            policy_number="AB12345678",
        )
        result = await orch.run_pipeline(record)
        assert result.status == ClaimStatus.ESCALATED
