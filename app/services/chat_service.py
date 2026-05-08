from app.config import settings
from app.embeddings.retriever import RetrieverService
from app.reranking.reranker import RerankerService
from app.services.helpers import ChatResult, _build_context, _document_to_source
from app.services.llm_service import LLMService
from app.services.cache_service import CacheService
from app.embeddings.factory import create_embeddings
from app.services.tracing_service import TracingService


class ChatService:
    def __init__(self):
        self._retriever = RetrieverService().get_retriever()
        self._llm_service = LLMService()
        self._cache_service = CacheService()
        self._embeddings = create_embeddings()
        self._reranker_service = RerankerService()
        self._tracing = TracingService()

    def answer_question(
        self, question: str, history: list[dict] | None = None
    ) -> ChatResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Frage darf nicht leer sein")

        has_history = bool(history)
        cache_hit = None
        query_vector = None

        with self._tracing.span(
            "chat.answer_question",
            input={
                "question": cleaned_question,
                "history_turns": len(history or []),
            },
            metadata={"cache_enabled": not has_history},
        ) as root_span:
            if not has_history:
                with self._tracing.span("chat.cache_lookup") as cache_span:
                    query_vector = self._embeddings.embed_query(cleaned_question)
                    cache_hit = self._cache_service.check_cache(query_vector)
                    self._tracing.update(cache_span, output={"hit": bool(cache_hit)})

            if cache_hit:
                cached_answer, cached_sources = cache_hit
                self._tracing.update(
                    root_span,
                    output={"answer": cached_answer, "cache_hit": True},
                )
                return ChatResult(
                    answer=cached_answer,
                    sources=[
                        {
                            "title": src.get("title"),
                            "doc_id": src.get("doc_id"),
                            "chunk_id": src.get("chunk_id"),
                            "heading_path": src.get("heading_path", []),
                            "url": src.get("url"),
                            "content": src.get("content"),
                        }
                        for src in cached_sources
                    ],
                )

            with self._tracing.span(
                "chat.retrieve",
                input={"question": cleaned_question},
            ) as retrieval_span:
                matches = self._retriever.invoke(cleaned_question)
                self._tracing.update(retrieval_span, output={"matches": len(matches)})

            if settings.reranker_enabled:
                with self._tracing.span(
                    "chat.rerank",
                    input={"matches": len(matches), "top_n": settings.reranker_top_n},
                ) as rerank_span:
                    matches = self._reranker_service.rerank(
                        cleaned_question,
                        matches,
                        top_n=settings.reranker_top_n,
                    )
                    self._tracing.update(rerank_span, output={"matches": len(matches)})

            context = _build_context(matches)
            callbacks = (
                [callback]
                if (callback := self._tracing.langchain_callback())
                else None
            )
            answer = self._llm_service.generate_answer(
                question=cleaned_question,
                context=context,
                history=history,
                callbacks=callbacks,
                metadata={
                    "langfuse_tags": ["chat"],
                    "cache_hit": False,
                    "retrieved_sources": len(matches),
                },
            )

            if not has_history:
                self._cache_service.save_to_cache(
                    query_text=cleaned_question,
                    query_embedding=query_vector,
                    llm_response=answer,
                    sources=matches,
                )

            self._tracing.update(
                root_span,
                output={"answer": answer, "cache_hit": False},
                metadata={"sources": len(matches)},
            )

        seen = set()
        return ChatResult(
            answer=answer,
            sources=[
                _document_to_source(m)
                for m in matches
                if not (doc_id := m.metadata.get("doc_id"))
                or (doc_id not in seen and not seen.add(doc_id))
            ],
        )
