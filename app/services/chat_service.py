from app.embeddings.retriever import RetrieverService
from app.services.helpers import ChatResult, _build_context, _document_to_source
from app.services.llm_service import LLMService
from app.services.cache_service import CacheService
from app.embeddings.factory import create_embeddings

class ChatService:
    def __init__(self):
        self._retriever = RetrieverService().get_retriever()
        self._llm_service = LLMService()
        self._cache_service = CacheService()
        self._embeddings = create_embeddings()

    def answer_question(
        self, question: str, history: list[dict] | None = None
    ) -> ChatResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Frage darf nicht leer sein")

        has_history = bool(history)
        cache_hit = None
        query_vector = None

        if not has_history:
            query_vector = self._embeddings.embed_query(cleaned_question)
            cache_hit = self._cache_service.check_cache(query_vector)

        if cache_hit:
            cached_answer, cached_sources = cache_hit
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

        matches = self._retriever.invoke(cleaned_question)
        context = _build_context(matches)
        answer = self._llm_service.generate_answer(
            question=cleaned_question,
            context=context,
            history=history,
        )

        if not has_history:
            self._cache_service.save_to_cache(
                query_text=cleaned_question,
                query_embedding=query_vector,
                llm_response=answer,
                sources=matches,
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
