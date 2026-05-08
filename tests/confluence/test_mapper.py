from datetime import datetime, timezone
import pytest
from app.confluence.mapper import _parse_datetime, map_attachment, map_page


def _base_payload(**kwargs):
    payload = {
        "id": "42",
        "title": "My Page",
        "status": "current",
        "space": {"id": 100},
        "body": {"storage": {"value": "<p>Hello</p>"}},
        "version": {"number": 3, "when": "2024-06-01T10:00:00Z"},
        "history": {"createdDate": "2024-01-01T00:00:00Z"},
        "_links": {"webui": "/pages/viewpage.action?pageId=42"},
        "ancestors": [],
    }
    payload.update(kwargs)
    return payload


class TestParseDatetime:
    def test_valid_iso_string(self):
        result = _parse_datetime("2024-06-01T10:00:00Z")
        assert result == datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_none_returns_none(self):
        assert _parse_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_datetime("") is None

    def test_z_suffix_replaced(self):
        result = _parse_datetime("2024-01-01T00:00:00Z")
        assert result is not None


class TestMapPage:
    def test_id_is_string(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.id == "42"

    def test_title(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.title == "My Page"

    def test_body_storage(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.body_storage == "<p>Hello</p>"

    def test_version_number(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.version == 3

    def test_relative_url_prepends_base(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.url.startswith("https://wiki.example.com")

    def test_absolute_url_unchanged(self):
        payload = _base_payload()
        payload["_links"]["webui"] = "https://other.example.com/pages/1"
        page = map_page(payload, base_url="https://wiki.example.com")
        assert page.url == "https://other.example.com/pages/1"

    def test_no_ancestors_parent_is_none(self):
        page = map_page(_base_payload(ancestors=[]), base_url="https://wiki.example.com")
        assert page.parent_id is None

    def test_with_ancestors_sets_parent(self):
        payload = _base_payload(ancestors=[{"id": 10}, {"id": 20}])
        page = map_page(payload, base_url="https://wiki.example.com")
        assert page.parent_id == "20"

    def test_space_id(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.space_id == "100"

    def test_created_at_parsed(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.created_at is not None

    def test_updated_at_parsed(self):
        page = map_page(_base_payload(), base_url="https://wiki.example.com")
        assert page.updated_at is not None


class TestMapAttachment:
    def test_maps_v1_attachment_metadata(self):
        payload = {
            "id": "att1",
            "title": "notes.txt",
            "metadata": {"mediaType": "text/plain"},
            "extensions": {"fileSize": 25},
            "version": {"number": 2, "when": "2024-06-01T10:00:00Z"},
            "_links": {
                "webui": "/download/attachments/42/notes.txt",
                "download": "/download/attachments/42/notes.txt?api=v2",
            },
        }

        attachment = map_attachment(
            payload,
            base_url="https://wiki.example.com",
            page_id="42",
            page_title="My Page",
            content=b"hello",
        )

        assert attachment.media_type == "text/plain"
        assert attachment.file_size == 25
        assert attachment.download_url == "https://wiki.example.com/download/attachments/42/notes.txt?api=v2"

    def test_maps_v2_attachment_shape(self):
        payload = {
            "id": "att1",
            "title": "manual.pdf",
            "pageId": "42",
            "mediaType": "application/pdf",
            "fileSize": 250,
            "webuiLink": "/wiki/download/attachments/42/manual.pdf",
            "downloadLink": "/wiki/download/attachments/42/manual.pdf?api=v2",
            "createdAt": "2024-01-01T00:00:00Z",
            "version": {"number": 3, "createdAt": "2024-06-01T10:00:00Z"},
            "_links": {},
        }

        attachment = map_attachment(
            payload,
            base_url="https://example.atlassian.net/wiki",
            page_id="fallback",
            page_title="My Page",
            content=b"%PDF",
        )

        assert attachment.page_id == "42"
        assert attachment.media_type == "application/pdf"
        assert attachment.file_size == 250
        assert attachment.download_url == "https://example.atlassian.net/wiki/download/attachments/42/manual.pdf?api=v2"
        assert attachment.created_at is not None
        assert attachment.updated_at is not None
