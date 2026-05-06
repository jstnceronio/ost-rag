import pytest
from pydantic import ValidationError
from app.api.models import (
    HistoryMessage, ChatRequest, ChatSource, ChatResponse,
    SyncRequest, SyncResponse,
)


class TestHistoryMessage:
    def test_valid_user_role(self):
        msg = HistoryMessage(role="user", content="Hello")
        assert msg.role == "user"

    def test_valid_assistant_role(self):
        msg = HistoryMessage(role="assistant", content="Hi")
        assert msg.role == "assistant"

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            HistoryMessage(role="system", content="Hi")

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            HistoryMessage(role="user", content="")

    def test_content_too_long_raises(self):
        with pytest.raises(ValidationError):
            HistoryMessage(role="user", content="x" * 501)


class TestChatRequest:
    def test_valid_request(self):
        req = ChatRequest(question="What is VPN?")
        assert req.question == "What is VPN?"
        assert req.history == []

    def test_empty_question_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="")

    def test_question_too_long_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest(question="q" * 2001)

    def test_history_accepted(self):
        req = ChatRequest(
            question="Follow-up?",
            history=[{"role": "user", "content": "Hello"}],
        )
        assert len(req.history) == 1

    def test_history_too_many_turns_raises(self):
        history = [{"role": "user", "content": "Hi"}] * 11
        with pytest.raises(ValidationError):
            ChatRequest(question="Q?", history=history)


class TestSyncRequest:
    def test_valid_request(self):
        req = SyncRequest(space_id="SPACE1")
        assert req.space_id == "SPACE1"
        assert req.limit is None

    def test_with_limit(self):
        req = SyncRequest(space_id="SPACE1", limit=50)
        assert req.limit == 50

    def test_zero_limit_raises(self):
        with pytest.raises(ValidationError):
            SyncRequest(space_id="SPACE1", limit=0)

    def test_negative_limit_raises(self):
        with pytest.raises(ValidationError):
            SyncRequest(space_id="SPACE1", limit=-1)


class TestSyncResponse:
    def test_fields(self):
        resp = SyncResponse(pages_indexed=10, chunks_indexed=42)
        assert resp.pages_indexed == 10
        assert resp.chunks_indexed == 42
