from unittest.mock import patch, Mock, MagicMock
import pytest


def _make_llm_service():
    with patch("app.services.llm_service.ChatOpenAI"):
        from app.services.llm_service import LLMService
        svc = LLMService()
        svc.llm = Mock()
        svc.llm.invoke.return_value = Mock(content="The answer is 42.")
        return svc


class TestGenerateAnswer:
    def test_returns_llm_content(self):
        svc = _make_llm_service()
        result = svc.generate_answer("What is the answer?", "Context here")
        assert result == "The answer is 42."

    def test_no_history_sends_two_messages(self):
        svc = _make_llm_service()
        svc.generate_answer("Q?", "ctx")
        messages = svc.llm.invoke.call_args[0][0]
        # SystemMessage + HumanMessage
        assert len(messages) == 2

    def test_history_injects_turns(self):
        svc = _make_llm_service()
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        svc.generate_answer("Follow-up?", "ctx", history=history)
        messages = svc.llm.invoke.call_args[0][0]
        # System + 2 history turns + final human
        assert len(messages) == 4

    def test_history_wrapped_in_delimiters(self):
        from langchain_core.messages import HumanMessage
        svc = _make_llm_service()
        history = [{"role": "user", "content": "my question"}]
        svc.generate_answer("Q?", "ctx", history=history)
        messages = svc.llm.invoke.call_args[0][0]
        history_msg = messages[1]
        assert "--- BEGIN HISTORY TURN ---" in history_msg.content
        assert "my question" in history_msg.content

    def test_question_wrapped_in_delimiters(self):
        svc = _make_llm_service()
        svc.generate_answer("What is VPN?", "ctx")
        messages = svc.llm.invoke.call_args[0][0]
        final_msg = messages[-1]
        assert "--- BEGIN QUESTION ---" in final_msg.content
        assert "What is VPN?" in final_msg.content

    def test_context_wrapped_in_delimiters(self):
        svc = _make_llm_service()
        svc.generate_answer("Q?", "my context block")
        messages = svc.llm.invoke.call_args[0][0]
        final_msg = messages[-1]
        assert "--- BEGIN CONTEXT ---" in final_msg.content
        assert "my context block" in final_msg.content

    def test_empty_history_sends_two_messages(self):
        svc = _make_llm_service()
        svc.generate_answer("Q?", "ctx", history=[])
        messages = svc.llm.invoke.call_args[0][0]
        assert len(messages) == 2

    def test_callbacks_and_metadata_passed_as_langchain_config(self):
        svc = _make_llm_service()
        callback = Mock()
        metadata = {"langfuse_tags": ["chat"]}

        svc.generate_answer("Q?", "ctx", callbacks=[callback], metadata=metadata)

        assert svc.llm.invoke.call_args.kwargs["config"] == {
            "callbacks": [callback],
            "metadata": metadata,
        }
