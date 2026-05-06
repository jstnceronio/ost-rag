from unittest.mock import Mock, patch
import pytest
from app.confluence.client import ConfluenceClient
from app.confluence.errors import ConfluenceAPIError


def _make_client():
    with patch("app.confluence.auth.build_session") as mock_build:
        mock_session = Mock()
        mock_build.return_value = mock_session
        client = ConfluenceClient(base_url="https://wiki.example.com", api_token="token")
        client.session = mock_session
        return client


def _ok_response(data: dict) -> Mock:
    resp = Mock()
    resp.ok = True
    resp.json.return_value = data
    return resp


def _error_response(status_code: int) -> Mock:
    resp = Mock()
    resp.ok = False
    resp.status_code = status_code
    resp.text = "Not Found"
    return resp


def _page_payload(page_id="1", title="Page"):
    return {
        "id": page_id,
        "title": title,
        "status": "current",
        "space": {"id": 100},
        "body": {"storage": {"value": "<p>content</p>"}},
        "version": {"number": 1, "when": "2024-01-01T00:00:00Z"},
        "history": {"createdDate": "2024-01-01T00:00:00Z"},
        "_links": {"webui": "/pages/viewpage.action?pageId=" + page_id},
        "ancestors": [],
    }


class TestGetPage:
    def test_returns_confluence_page(self):
        client = _make_client()
        client.session.get.return_value = _ok_response(_page_payload("42", "My Page"))
        page = client.get_page("42")
        assert page.id == "42"
        assert page.title == "My Page"

    def test_raises_on_api_error(self):
        client = _make_client()
        client.session.get.return_value = _error_response(404)
        with pytest.raises(ConfluenceAPIError) as exc:
            client.get_page("99")
        assert exc.value.status_code == 404


class TestGetPageTree:
    def test_returns_root_and_child_pages(self):
        client = _make_client()
        client.session.get.side_effect = [
            _ok_response(_page_payload("1", "Root")),
            _ok_response({"results": [_page_payload("2", "Child")]}),
            _ok_response({"results": []}),
        ]

        pages = client.get_page_tree("1")

        assert [page.id for page in pages] == ["1", "2"]

    def test_recurses_into_child_pages(self):
        client = _make_client()
        client.session.get.side_effect = [
            _ok_response(_page_payload("1", "Root")),
            _ok_response({"results": [_page_payload("2", "Child")]}),
            _ok_response({"results": [_page_payload("3", "Grandchild")]}),
            _ok_response({"results": []}),
        ]

        pages = client.get_page_tree("1")

        assert [page.id for page in pages] == ["1", "2", "3"]

    def test_respects_limit(self):
        client = _make_client()
        client.session.get.return_value = _ok_response(_page_payload("1", "Root"))

        pages = client.get_page_tree("1", limit=1)

        assert [page.id for page in pages] == ["1"]
        assert client.session.get.call_count == 1


class TestGetPagesBySpaceId:
    def test_returns_pages(self):
        client = _make_client()
        client.session.get.return_value = _ok_response(
            {"results": [_page_payload("1"), _page_payload("2")]}
        )
        pages = client.get_pages_by_space_id("SPACE1")
        assert len(pages) == 2

    def test_respects_limit(self):
        client = _make_client()
        client.session.get.return_value = _ok_response({"results": [_page_payload("1")]})
        pages = client.get_pages_by_space_id("SPACE1", limit=1)
        # With limit=1 the batch size requested to the API is 1
        call_params = client.session.get.call_args[1]["params"]
        assert call_params["limit"] == 1

    def test_stops_when_fewer_results_than_batch(self):
        client = _make_client()
        # Returns 2 results with batch_size 100 → no more pages
        client.session.get.return_value = _ok_response(
            {"results": [_page_payload("1"), _page_payload("2")]}
        )
        pages = client.get_pages_by_space_id("SPACE1")
        assert client.session.get.call_count == 1

    def test_paginates_until_limit(self):
        client = _make_client()
        batch = [_page_payload(str(i)) for i in range(5)]
        client.session.get.return_value = _ok_response({"results": batch})
        pages = client.get_pages_by_space_id("SPACE1", page_size=5, limit=10)
        assert client.session.get.call_count == 2
