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
            mock_client_cls.return_value.get_attachments_for_pages.return_value = []
            mock_idx_cls.return_value.index_chunks.return_value = None

            page_count, chunk_count = run_sync("SPACE1")

        assert page_count == 2
        assert chunk_count >= 2  # at least one chunk per page

    def test_respects_limit_argument(self):
        pages = [_make_page("1")]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = pages
            mock_client_cls.return_value.get_attachments_for_pages.return_value = []
            mock_idx_cls.return_value.index_chunks.return_value = None

            run_sync("SPACE1", limit=1)

        mock_client_cls.return_value.get_pages_by_space_id.assert_called_once_with(
            space_id="SPACE1", limit=1
        )

    def test_syncs_page_tree_when_page_id_is_provided(self):
        pages = [_make_page("1"), _make_page("2")]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_page_tree.return_value = pages
            mock_client_cls.return_value.get_attachments_for_pages.return_value = []
            mock_idx_cls.return_value.index_chunks.return_value = None

            page_count, chunk_count = run_sync(page_id="1")

        assert page_count == 2
        assert chunk_count >= 2
        mock_client_cls.return_value.get_page_tree.assert_called_once_with(
            page_id="1", limit=None
        )
        mock_client_cls.return_value.get_pages_by_space_id.assert_not_called()

    def test_empty_pages_returns_zero_counts(self):
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = []
            mock_client_cls.return_value.get_attachments_for_pages.return_value = []
            mock_idx_cls.return_value.index_chunks.return_value = None

            page_count, chunk_count = run_sync("SPACE1")

        assert page_count == 0
        assert chunk_count == 0
        mock_idx_cls.assert_not_called()

    def test_index_chunks_called(self):
        pages = [_make_page("1")]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = pages
            mock_client_cls.return_value.get_attachments_for_pages.return_value = []
            mock_idx_cls.return_value.index_chunks.return_value = None

            run_sync("SPACE1")

        mock_idx_cls.return_value.index_chunks.assert_called_once()

    def test_indexes_supported_attachments(self):
        from tests.conftest import make_confluence_attachment

        pages = [_make_page("1")]
        attachments = [
            make_confluence_attachment(
                id="att1",
                page_id="1",
                page_title="Page",
                title="notes.txt",
                content=b"Attachment content",
            )
        ]
        with patch("app.services.sync_service.ConfluenceClient") as mock_client_cls, \
             patch("app.services.sync_service.IndexingService") as mock_idx_cls:

            mock_client_cls.return_value.get_pages_by_space_id.return_value = pages
            mock_client_cls.return_value.get_attachments_for_pages.return_value = attachments
            mock_idx_cls.return_value.index_chunks.return_value = None

            page_count, chunk_count = run_sync("SPACE1")

        assert page_count == 1
        assert chunk_count >= 2
        indexed_chunks = mock_idx_cls.return_value.index_chunks.call_args.args[0]
        assert any("Attachment content" in chunk.text for chunk in indexed_chunks)
