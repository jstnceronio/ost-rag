from unittest.mock import Mock
import pytest
from starlette.testclient import TestClient

from app.api.chat import app, get_chat_service
from app.api.deps import verify_api_key
from app.services.helpers import ChatResult


def _make_mock_service():
    mock_svc = Mock()
    mock_svc.answer_question.return_value = ChatResult(
        answer="Here is the answer.",
        sources=[{"title": "T", "doc_id": "1", "chunk_id": "1:0", "heading_path": [], "url": None}],
    )
    return mock_svc


@pytest.fixture
def mock_service():
    return _make_mock_service()


@pytest.fixture
def client(mock_service):
    app.dependency_overrides[verify_api_key] = lambda: None
    app.dependency_overrides[get_chat_service] = lambda: mock_service
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestChatEndpoint:
    def test_valid_request_returns_200(self, client):
        resp = client.post("/chat", json={"question": "What is VPN?"})
        assert resp.status_code == 200

    def test_response_has_answer_and_sources(self, client):
        resp = client.post("/chat", json={"question": "What is VPN?"})
        data = resp.json()
        assert "answer" in data
        assert "sources" in data

    def test_missing_api_key_returns_401(self):
        with TestClient(app) as c:
            resp = c.post("/chat", json={"question": "Q?"})
        assert resp.status_code == 401

    def test_empty_question_returns_422(self, client):
        resp = client.post("/chat", json={"question": ""})
        assert resp.status_code == 422

    def test_question_too_long_returns_422(self, client):
        resp = client.post("/chat", json={"question": "q" * 2001})
        assert resp.status_code == 422

    def test_with_history(self, client, mock_service):
        resp = client.post("/chat", json={
            "question": "Follow-up?",
            "history": [{"role": "user", "content": "Hello"}],
        })
        assert resp.status_code == 200

    def test_value_error_from_service_returns_400(self, client, mock_service):
        mock_service.answer_question.side_effect = ValueError("bad input")
        resp = client.post("/chat", json={"question": "Q?"})
        assert resp.status_code == 400
