"""Azure AI Search service for Foundry IQ — policies and claims history indexes.

Provides two indexes:
- policies-index: policy holder details, coverage info, active dates
- claims-history-index: prior claims for fraud pattern analysis

All Azure calls are mockable for unit testing.
"""

from __future__ import annotations

import logging
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

POLICIES_INDEX = "policies-index"
CLAIMS_HISTORY_INDEX = "claims-history-index"


def _policy_index_schema() -> SearchIndex:
    """Define the policies index schema."""
    fields = [
        SimpleField(name="policy_number", type=SearchFieldDataType.String, key=True),
        SearchableField(name="policy_holder_name", type=SearchFieldDataType.String),
        SimpleField(name="vehicle_make", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="vehicle_model", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="vehicle_year", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="vin", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="coverage_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="coverage_limit", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="deductible", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="policy_start_date", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="policy_expiry_date", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="status", type=SearchFieldDataType.String, filterable=True),
    ]
    return SearchIndex(name=POLICIES_INDEX, fields=fields)


def _claims_history_index_schema() -> SearchIndex:
    """Define the claims history index schema."""
    fields = [
        SimpleField(name="claim_id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="policy_holder_name", type=SearchFieldDataType.String),
        SimpleField(name="policy_number", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="vin", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="claim_type", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="claim_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="claim_amount", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="outcome", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="fraud_flagged", type=SearchFieldDataType.Boolean, filterable=True),
    ]
    return SearchIndex(name=CLAIMS_HISTORY_INDEX, fields=fields)


class SearchService:
    """Azure AI Search wrapper for policies and claims history lookup."""

    def __init__(
        self,
        endpoint: str | None = None,
        credential: Any | None = None,
    ) -> None:
        settings = get_settings()
        self._endpoint = endpoint or settings.azure_search_endpoint
        self._credential = credential or DefaultAzureCredential()
        self._index_client: SearchIndexClient | None = None

    def _get_index_client(self) -> SearchIndexClient:
        if self._index_client is None:
            self._index_client = SearchIndexClient(
                endpoint=self._endpoint, credential=self._credential
            )
        return self._index_client

    def _get_search_client(self, index_name: str) -> SearchClient:
        return SearchClient(
            endpoint=self._endpoint,
            index_name=index_name,
            credential=self._credential,
        )

    def create_or_update_indexes(self) -> None:
        """Create or update both search indexes."""
        client = self._get_index_client()
        client.create_or_update_index(_policy_index_schema())
        logger.info("Created/updated index %s", POLICIES_INDEX)
        client.create_or_update_index(_claims_history_index_schema())
        logger.info("Created/updated index %s", CLAIMS_HISTORY_INDEX)

    def upload_policy_records(self, records: list[dict[str, Any]]) -> None:
        """Upload policy records to the policies index."""
        client = self._get_search_client(POLICIES_INDEX)
        result = client.upload_documents(documents=records)
        logger.info("Uploaded %d policy records", len(records))
        return result

    def upload_claim_history_records(self, records: list[dict[str, Any]]) -> None:
        """Upload prior claim records to the claims history index."""
        client = self._get_search_client(CLAIMS_HISTORY_INDEX)
        result = client.upload_documents(documents=records)
        logger.info("Uploaded %d claim history records", len(records))
        return result

    def lookup_policy(self, policy_number: str) -> dict[str, Any] | None:
        """Look up a policy by exact policy number.

        Returns the first matching policy record, or None.
        """
        client = self._get_search_client(POLICIES_INDEX)
        results = client.search(
            search_text="",
            filter=f"policy_number eq '{policy_number}'",
            top=1,
        )
        for r in results:
            return dict(r)
        return None

    def search_prior_claims(
        self,
        policy_holder_name: str | None = None,
        vin: str | None = None,
        policy_number: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for prior claims matching given criteria.

        At least one of policy_holder_name, vin, or policy_number must be provided.
        Returns matching claim history records sorted by claim_date descending.
        """
        filters = []
        if policy_holder_name:
            filters.append(f"policy_holder_name eq '{policy_holder_name}'")
        if vin:
            filters.append(f"vin eq '{vin}'")
        if policy_number:
            filters.append(f"policy_number eq '{policy_number}'")

        if not filters:
            return []

        client = self._get_search_client(CLAIMS_HISTORY_INDEX)
        results = client.search(
            search_text="",
            filter=" or ".join(filters),
            order_by=["claim_date desc"],
            top=20,
        )
        return [dict(r) for r in results]
