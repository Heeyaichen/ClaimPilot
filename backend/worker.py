"""Service Bus queue worker — processes claims from the ingestion queue.

Run with: python -m backend.worker
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient

from backend.core.config import get_settings
from backend.models.claim import ClaimStatus
from backend.pipeline.orchestrator import ClaimOrchestrator
from backend.services.claim_state_store import ClaimStateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5


def _process_claim(message_body: str) -> None:
    """Process a single claim message from the queue."""
    body = json.loads(message_body)
    claim_id = body.get("claim_id")
    logger.info("Processing claim %s from Service Bus", claim_id)

    store = ClaimStateStore()
    record = store.get_claim(claim_id)
    if record is None:
        logger.error("Claim %s not found in Cosmos DB", claim_id)
        return

    orchestrator = ClaimOrchestrator(state_store=store)
    try:
        asyncio.run(orchestrator.run_pipeline(record))
        logger.info("Pipeline completed for claim %s", claim_id)
    except Exception:
        logger.exception("Pipeline failed for claim %s", claim_id)
        store.mark_claim_status(claim_id, ClaimStatus.FAILED)


def main() -> None:
    """Main worker loop — poll Service Bus and process claims."""
    logger.info("ClaimPilot worker starting...")
    settings = get_settings()
    queue_name = os.environ.get("AZURE_SERVICE_BUS_QUEUE_NAME", "claims-ingestion")
    logger.info("Listening on queue: %s", queue_name)

    client = ServiceBusClient(
        fully_qualified_namespace=settings.azure_service_bus_namespace,
        credential=DefaultAzureCredential(),
    )
    receiver = client.get_queue_receiver(queue_name=queue_name)

    try:
        while True:
            messages = receiver.receive_messages(
                max_message_count=1,
                max_wait_time=POLL_INTERVAL_SECONDS,
            )
            for msg in messages:
                try:
                    _process_claim(str(msg))
                    receiver.complete_message(msg)
                except Exception:
                    logger.exception("Error processing message")
                    receiver.abandon_message(msg)
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
    finally:
        receiver.close()
        client.close()


if __name__ == "__main__":
    main()
