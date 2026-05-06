from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from app.api.chat import app
from app.api.deps import verify_api_key


@pytest.fixture
def client():
    app.dependency_overrides[verify_api_key] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestSyncEndpoint:
    def test_valid_request_returns_200(self, client):
        with patch("app.api.sync.run_sync", return_value=(5, 40)):
            resp = client.post("/sync", json={"space_id": "SPACE1"})
        assert resp.status_code == 200

    def test_response_contains_counts(self, client):
        with patch("app.api.sync.run_sync", return_value=(5, 40)):
            resp = client.post("/sync", json={"space_id": "SPACE1"})
        data = resp.json()
        assert data["pages_indexed"] == 5
        assert data["chunks_indexed"] == 40

    def test_with_limit(self, client):
        with patch("app.api.sync.run_sync", return_value=(2, 10)) as mock_sync:
            resp = client.post("/sync", json={"space_id": "SPACE1", "limit": 2})
        assert resp.status_code == 200
        mock_sync.assert_called_once_with(space_id="SPACE1", page_id=None, limit=2)

    def test_with_page_id(self, client):
        with patch("app.api.sync.run_sync", return_value=(3, 12)) as mock_sync:
            resp = client.post("/sync", json={"page_id": "123"})
        assert resp.status_code == 200
        mock_sync.assert_called_once_with(space_id=None, page_id="123", limit=None)

    def test_no_pages_found_returns_404(self, client):
        with patch("app.api.sync.run_sync", return_value=(0, 0)):
            resp = client.post("/sync", json={"space_id": "EMPTY"})
        assert resp.status_code == 404

    def test_missing_api_key_returns_401(self):
        resp = TestClient(app).post("/sync", json={"space_id": "SPACE1"})
        assert resp.status_code == 401

    def test_missing_space_id_returns_422(self, client):
        resp = client.post("/sync", json={})
        assert resp.status_code == 422

    def test_negative_limit_returns_422(self, client):
        resp = client.post("/sync", json={"space_id": "SPACE1", "limit": -1})
        assert resp.status_code == 422
