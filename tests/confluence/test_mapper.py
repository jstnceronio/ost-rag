from datetime import datetime, timezone
import pytest
from app.confluence.mapper import _parse_datetime, map_page


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
