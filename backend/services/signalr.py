"""SignalR broadcaster for real-time pipeline step events."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class SignalRBroadcaster:
    """Broadcasts pipeline step events via Azure SignalR Service REST API."""

    def __init__(
        self,
        endpoint: str | None = None,
        hub_name: str = "claims",
        credential: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = (endpoint or settings.azure_signalr_connection).rstrip("/")
        self._hub_name = hub_name
        self._credential = credential or DefaultAzureCredential()

    def _build_url(self) -> str:
        """Build the SignalR REST API URL for the hub."""
        # Azure SignalR REST API: POST /api/v1/hubs/{hub}
        if self._endpoint.startswith("http"):
            return f"{self._endpoint}/api/v1/hubs/{self._hub_name}"
        # Connection string format — extract endpoint
        return f"https://{self._endpoint}/api/v1/hubs/{self._hub_name}"

    def broadcast_step_event(
        self,
        claim_id: str,
        step: str,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast a pipeline step event to all connected SignalR clients.

        Args:
            claim_id: The claim identifier.
            step: Pipeline step name (e.g., "INGEST_DOCUMENT").
            status: Event status: "stepStarted", "stepCompleted", or "stepFailed".
            payload: Optional additional data (output, error, duration).
        """
        event = {
            "type": status,
            "claimId": claim_id,
            "step": step,
            **(payload or {}),
        }

        try:
            token = self._credential.get_token("https://signalr.service.azure.com/.default")
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    self._build_url(),
                    headers={
                        "Authorization": f"Bearer {token.token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "target": "pipelineEvent",
                        "arguments": [json.dumps(event)],
                    },
                )
                resp.raise_for_status()
            logger.info("Broadcast %s for claim %s step %s", status, claim_id, step)
        except Exception:
            # SignalR broadcast failure should not block the pipeline
            logger.exception("Failed to broadcast SignalR event for claim %s", claim_id)
