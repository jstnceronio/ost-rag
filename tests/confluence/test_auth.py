import pytest
from app.confluence.auth import build_session


def test_build_session_sets_bearer_token():
    session = build_session("my-token")
    assert session.headers["Authorization"] == "Bearer my-token"


def test_build_session_sets_accept_header():
    session = build_session("my-token")
    assert session.headers["Accept"] == "application/json"


def test_build_session_sets_user_agent():
    session = build_session("my-token")
    assert "confluence-rag-bot" in session.headers["User-Agent"]


def test_build_session_raises_without_token():
    with pytest.raises(ValueError, match="token"):
        build_session(None)
