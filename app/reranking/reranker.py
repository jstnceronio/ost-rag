import json
from pydantic import ValidationError
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.reranking.helpers import _build_prompt
from app.reranking.models import RerankResponse


class RerankerService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

    def rerank(self, query: str, docs: list[Document], top_n: int = 8) -> list[Document]:
        if not docs:
            return []

        prompt = _build_prompt(query=query, docs=docs, top_n=top_n)
        response = self.llm.invoke([
            SystemMessage(content="Du bist ein strikter JSON-Reranker. Antworte nur mit validem JSON."),
            HumanMessage(content=prompt),
        ])

        try:
            payload = json.loads(str(response.content))
            parsed = RerankResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError):
            return docs[:top_n]

        selected: list[Document] = []
        seen: set[int] = set()

        for result in parsed.results:
            if result.index in seen:
                continue
            if not result.supports_answer:
                continue
            if result.index < 0 or result.index >= len(docs):
                continue

            seen.add(result.index)
            selected.append(docs[result.index])

            if len(selected) >= top_n:
                break

        return selected
