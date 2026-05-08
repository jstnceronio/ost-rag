from contextlib import nullcontext
from unittest.mock import Mock, patch
import pytest
from langchain_core.documents import Document
from app.services.helpers import ChatResult


def _doc(**meta) -> Document:
    return Document(page_content="content", metadata={"doc_id": "1", "chunk_id": "1:0", "title": "T", "heading_path": [], **meta})


def _make_chat_service(answer="The answer.", cache_hit=None, matches=None):
    if matches is None:
        matches = [_doc()]

    mock_retriever = Mock()
    mock_retriever.invoke.return_value = matches

    mock_llm = Mock()
    mock_llm.generate_answer.return_value = answer

    mock_cache = Mock()
    mock_cache.check_cache.return_value = cache_hit

    mock_embeddings = Mock()
    mock_embeddings.embed_query.return_value = [0.1, 0.2]

    with patch("app.services.chat_service.RetrieverService") as mock_ret_cls, \
         patch("app.services.chat_service.LLMService") as mock_llm_cls, \
         patch("app.services.chat_service.CacheService") as mock_cache_cls, \
         patch("app.services.chat_service.create_embeddings") as mock_emb, \
         patch("app.services.chat_service.RerankerService") as mock_reranker_cls:

        mock_ret_cls.return_value.get_retriever.return_value = mock_retriever
        mock_llm_cls.return_value = mock_llm
        mock_cache_cls.return_value = mock_cache
        mock_emb.return_value = mock_embeddings
        mock_reranker = Mock()
        mock_reranker.rerank.return_value = matches
        mock_reranker_cls.return_value = mock_reranker

        from app.services.chat_service import ChatService
        svc = ChatService()
        svc._retriever = mock_retriever
        svc._llm_service = mock_llm
        svc._cache_service = mock_cache
        svc._embeddings = mock_embeddings
        svc._reranker_service = mock_reranker

    return svc


class TestAnswerQuestion:
    def test_empty_question_raises_value_error(self):
        svc = _make_chat_service()
        with pytest.raises(ValueError):
            svc.answer_question("   ")

    def test_cache_hit_returns_cached_answer(self):
        cached_sources = [{"title": "T", "doc_id": "1", "chunk_id": "1:0", "heading_path": [], "url": None}]
        svc = _make_chat_service(cache_hit=("cached!", cached_sources))
        result = svc.answer_question("What is VPN?")
        assert result.answer == "cached!"

    def test_cache_miss_calls_llm(self):
        svc = _make_chat_service(answer="Fresh answer.")
        result = svc.answer_question("What is VPN?")
        assert result.answer == "Fresh answer."

    def test_with_history_skips_cache(self):
        svc = _make_chat_service(answer="Answer with history.")
        result = svc.answer_question("Follow-up?", history=[{"role": "user", "content": "Hi"}])
        svc._cache_service.check_cache.assert_not_called()
        assert result.answer == "Answer with history."

    def test_result_sources_deduplicated_by_doc_id(self):
        matches = [_doc(doc_id="1"), _doc(doc_id="1"), _doc(doc_id="2")]
        svc = _make_chat_service(matches=matches)
        result = svc.answer_question("Q?")
        doc_ids = [s["doc_id"] for s in result.sources]
        assert doc_ids.count("1") == 1

    def test_saves_to_cache_on_miss(self):
        svc = _make_chat_service()
        svc.answer_question("What is VPN?")
        svc._cache_service.save_to_cache.assert_called_once()

    def test_does_not_save_cache_when_history_present(self):
        svc = _make_chat_service()
        svc.answer_question("Q?", history=[{"role": "user", "content": "Hi"}])
        svc._cache_service.save_to_cache.assert_not_called()

    def test_passes_langfuse_callback_to_llm_when_tracing_enabled(self):
        svc = _make_chat_service()
        callback = Mock()
        tracer = Mock()
        tracer.span.return_value = nullcontext(None)
        tracer.langchain_callback.return_value = callback
        svc._tracing = tracer

        svc.answer_question("What is VPN?")

        call_kwargs = svc._llm_service.generate_answer.call_args.kwargs
        assert call_kwargs["callbacks"] == [callback]
        assert call_kwargs["metadata"]["langfuse_tags"] == ["chat"]
