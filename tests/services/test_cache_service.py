from unittest.mock import Mock, patch
import pytest
from app.services.cache_service import CacheService


def _service_no_supabase():
    with patch("app.services.cache_service.settings") as mock_settings:
        mock_settings.supabase_url = None
        mock_settings.supabase_service_key = None
        mock_settings.supabase_table_name = "documents"
        with patch("app.services.cache_service.create_embeddings"):
            svc = CacheService()
            svc.supabase_client = None
    return svc


def _service_with_supabase():
    mock_client = Mock()
    with patch("app.services.cache_service.create_embeddings"):
        with patch("app.services.cache_service.settings") as mock_settings:
            mock_settings.supabase_url = "https://supabase.example.com"
            mock_settings.supabase_service_key = "key"
            mock_settings.supabase_table_name = "documents"
            svc = CacheService.__new__(CacheService)
            svc.supabase_client = mock_client
            svc.embeddings = Mock()
    return svc, mock_client


class TestCheckCache:
    def test_no_client_returns_none(self):
        svc = _service_no_supabase()
        assert svc.check_cache([0.1, 0.2]) is None

    def test_no_data_returns_none(self):
        svc, client = _service_with_supabase()
        client.rpc.return_value.execute.return_value = Mock(data=[])
        assert svc.check_cache([0.1, 0.2]) is None

    def test_cache_hit_valid_sources_returns_tuple(self):
        svc, client = _service_with_supabase()
        client.rpc.return_value.execute.return_value = Mock(data=[{
            "id": "abc",
            "llm_response": "cached answer",
            "source_metadata": [],
        }])
        result = svc.check_cache([0.1, 0.2])
        assert result == ("cached answer", [])


class TestSaveToCache:
    def test_no_client_is_noop(self):
        svc = _service_no_supabase()
        # Should not raise
        svc.save_to_cache("question", [0.1], "answer", [])

    def test_inserts_into_semantic_cache(self):
        svc, client = _service_with_supabase()
        client.table.return_value.insert.return_value.execute.return_value = Mock()
        svc.save_to_cache("question", [0.1], "answer", [])
        client.table.assert_called_with("semantic_cache")


class TestValidateSources:
    def test_empty_sources_returns_true(self):
        svc, _ = _service_with_supabase()
        assert svc._validate_sources([]) is True

    def test_no_client_returns_false(self):
        svc = _service_no_supabase()
        assert svc._validate_sources([{"doc_id": "1", "version": 1}]) is False


class TestDeleteExpiredCache:
    def test_no_client_is_noop(self):
        svc = _service_no_supabase()
        svc._delete_expired_cache("some-id")  # Should not raise

    def test_deletes_by_id(self):
        svc, client = _service_with_supabase()
        client.table.return_value.delete.return_value.eq.return_value.execute.return_value = Mock()
        svc._delete_expired_cache("abc-123")
        client.table.assert_called_with("semantic_cache")
