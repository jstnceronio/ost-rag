from unittest.mock import patch, Mock
import pytest
from app.services.sync_service import run_sync


def _make_page(page_id="1"):
    from app.confluence.models import ConfluencePage
    from datetime import datetime
    return ConfluencePage(
        id=page_id, title="Page", space_id="S1", parent_id=None,
        status="current", url="https://wiki.example.com/pages/" + page_id,
        body_storage="<p>content</p>", version=1,
        created_at=datetime(2024, 1, 1), updated_at=datetime(2024, 6, 1),
    )


class TestRunSync:
    def test_returns_page_and_chunk_counts(self):
        pages = [_make_page("1"), _make_page("2")]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = pages
            mock_idx_cls.return_value.index_chunks.return_value = None

            page_count, chunk_count = run_sync("SPACE1")

        assert page_count == 2
        assert chunk_count >= 2  # at least one chunk per page

    def test_respects_limit_argument(self):
        pages = [_make_page("1")]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = pages
            mock_idx_cls.return_value.index_chunks.return_value = None

            run_sync("SPACE1", limit=1)

        mock_client_cls.return_value.get_pages_by_space_id.assert_called_once_with(
            space_id="SPACE1", limit=1
        )

    def test_empty_pages_returns_zero_counts(self):
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = []
            mock_idx_cls.return_value.index_chunks.return_value = None

            page_count, chunk_count = run_sync("SPACE1")

        assert page_count == 0
        assert chunk_count == 0

    def test_index_chunks_called(self):
        pages = [_make_page("1")]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = pages
            mock_idx_cls.return_value.index_chunks.return_value = None

            run_sync("SPACE1")

        mock_idx_cls.return_value.index_chunks.assert_called_once()
