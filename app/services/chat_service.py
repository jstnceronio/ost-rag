from app.embeddings.retriever import RetrieverService
from app.services.helpers import ChatResult, _build_context, _document_to_source
from app.services.llm_service import LLMService


class ChatService:
    def __init__(self):
        self._retriever = RetrieverService().get_retriever()
        self._llm_service = LLMService()

    def answer_question(self, question: str) -> ChatResult:
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Frage darf nicht leer sein")

        matches = self._retriever.invoke(cleaned_question)
        context = _build_context(matches)
        answer = self._llm_service.generate_answer(
            question=cleaned_question,
            context=context,
        )

        return ChatResult(
            answer=answer,
            sources=[_document_to_source(match) for match in matches],
        )
