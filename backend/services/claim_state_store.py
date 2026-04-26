"""Cosmos DB-backed claim state store for pipeline persistence."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from azure.cosmos import CosmosClient
from azure.cosmos.container import ContainerProxy
from azure.identity import DefaultAzureCredential

from backend.core.config import get_settings
from backend.models.claim import (
    STEP_TO_CLAIM_STATUS,
    ClaimRecord,
    ClaimStatus,
    PipelineStep,
    PipelineStepState,
    StepStatus,
)

logger = logging.getLogger(__name__)

DATABASE_NAME = "claimpilot-db"
CONTAINER_NAME = "claims"


class ClaimStateStore:
    """Persists claim records and step state in Azure Cosmos DB."""

    def __init__(
        self,
        endpoint: str | None = None,
        credential: Any | None = None,
        database_name: str = DATABASE_NAME,
        container_name: str = CONTAINER_NAME,
    ) -> None:
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_cosmos_endpoint
        self._credential = credential or DefaultAzureCredential()
        self._database_name = database_name
        self._container_name = container_name
        self._container: ContainerProxy | None = None

    def _get_container(self) -> ContainerProxy:
        """Lazy-initialize the Cosmos container reference."""
        if self._container is None:
            client = CosmosClient(url=self._endpoint, credential=self._credential)
            database = client.get_database_client(self._database_name)
            self._container = database.get_container_client(self._container_name)
        return self._container

    def create_claim(self, record: ClaimRecord) -> ClaimRecord:
        """Create a new claim record in Cosmos DB.

        Initializes all 7 pipeline steps as PENDING.
        """
        if not record.steps:
            record.steps = [
                PipelineStepState(step=step) for step in PipelineStep
            ]
        record.updated_at = datetime.utcnow()
        self._get_container().upsert_item(body=record.model_dump(mode="json"))
        logger.info("Created claim %s", record.claim_id)
        return record

    def get_claim(self, claim_id: str) -> ClaimRecord | None:
        """Retrieve a claim record by ID using cross-partition query."""
        try:
            query = "SELECT * FROM c WHERE c.claim_id = @claim_id"
            params = [{"name": "@claim_id", "value": claim_id}]
            items = list(
                self._get_container().query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True,
                )
            )
            if not items:
                return None
            return ClaimRecord.model_validate(items[0])
        except Exception:
            logger.warning("Claim %s not found", claim_id)
            return None

    def update_step(
        self,
        claim_id: str,
        step: PipelineStep,
        status: StepStatus,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ClaimRecord | None:
        """Update a specific pipeline step's status and optionally its output.

        Also updates the top-level claim status based on step progression.
        """
        record = self.get_claim(claim_id)
        if record is None:
            logger.error("Cannot update step: claim %s not found", claim_id)
            return None

        now = datetime.utcnow()
        for step_state in record.steps:
            if step_state.step == step:
                step_state.status = status
                if status == StepStatus.RUNNING:
                    step_state.started_at = now
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    step_state.completed_at = now
                if output is not None:
                    step_state.output = output
                if error is not None:
                    step_state.error = error
                break

        # Update top-level claim status
        if status == StepStatus.RUNNING and step in STEP_TO_CLAIM_STATUS:
            record.status = STEP_TO_CLAIM_STATUS[step]
        elif status == StepStatus.FAILED:
            record.status = ClaimStatus.FAILED

        record.updated_at = now
        self._get_container().upsert_item(body=record.model_dump(mode="json"))
        logger.info("Updated claim %s step %s → %s", claim_id, step.value, status.value)
        return record

    def mark_claim_status(self, claim_id: str, status: ClaimStatus) -> ClaimRecord | None:
        """Update only the top-level claim status."""
        record = self.get_claim(claim_id)
        if record is None:
            return None
        record.status = status
        record.updated_at = datetime.utcnow()
        self._get_container().upsert_item(body=record.model_dump(mode="json"))
        logger.info("Marked claim %s → %s", claim_id, status.value)
        return record
