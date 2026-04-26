"""Unit tests for Azure Search service — mocked SDK calls."""

from unittest.mock import MagicMock, patch

from backend.services.search import (
    SearchService,
)


def _make_service() -> tuple[SearchService, MagicMock]:
    """Create SearchService with mocked index and search clients."""
    service = SearchService.__new__(SearchService)
    service._endpoint = "https://mock.search.azure.com"
    service._credential = MagicMock()
    service._index_client = None
    return service


def test_create_or_update_indexes():
    service = _make_service()
    mock_ic = MagicMock()
    service._index_client = mock_ic

    service.create_or_update_indexes()

    assert mock_ic.create_or_update_index.call_count == 2


def test_upload_policy_records():
    service = _make_service()
    records = [{"policy_number": "AB12345678"}]

    with patch.object(service, "_get_search_client") as mock_sc:
        client = MagicMock()
        mock_sc.return_value = client
        service.upload_policy_records(records)
        client.upload_documents.assert_called_once_with(documents=records)


def test_upload_claim_history_records():
    service = _make_service()
    records = [{"claim_id": "CLM-000001"}]

    with patch.object(service, "_get_search_client") as mock_sc:
        client = MagicMock()
        mock_sc.return_value = client
        service.upload_claim_history_records(records)
        client.upload_documents.assert_called_once_with(documents=records)


def test_lookup_policy_found():
    service = _make_service()
    mock_result = {"policy_number": "AB12345678", "status": "ACTIVE"}

    with patch.object(service, "_get_search_client") as mock_sc:
        client = MagicMock()
        client.search.return_value = iter([mock_result])
        mock_sc.return_value = client

        result = service.lookup_policy("AB12345678")
        assert result == mock_result
        client.search.assert_called_once_with(
            search_text="",
            filter="policy_number eq 'AB12345678'",
            top=1,
        )


def test_lookup_policy_not_found():
    service = _make_service()

    with patch.object(service, "_get_search_client") as mock_sc:
        client = MagicMock()
        client.search.return_value = iter([])
        mock_sc.return_value = client

        result = service.lookup_policy("MISSING")
        assert result is None


def test_search_prior_claims_by_vin():
    service = _make_service()
    claims = [{"claim_id": "CLM-000001"}]

    with patch.object(service, "_get_search_client") as mock_sc:
        client = MagicMock()
        client.search.return_value = iter(claims)
        mock_sc.return_value = client

        result = service.search_prior_claims(vin="1HGCG5655WA012345")
        assert len(result) == 1
        client.search.assert_called_once_with(
            search_text="",
            filter="vin eq '1HGCG5655WA012345'",
            order_by=["claim_date desc"],
            top=20,
        )


def test_search_prior_claims_combined_filters():
    service = _make_service()

    with patch.object(service, "_get_search_client") as mock_sc:
        client = MagicMock()
        client.search.return_value = iter([])
        mock_sc.return_value = client

        result = service.search_prior_claims(
            policy_number="AB12345678",
            vin="1HGCG5655WA012345",
        )
        assert result == []
        call_args = client.search.call_args
        # Should combine with "or"
        assert " or " in call_args.kwargs["filter"]


def test_search_prior_claims_no_filters():
    service = _make_service()
    result = service.search_prior_claims()
    assert result == []
