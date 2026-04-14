from langchain_openai import ChatOpenAI
from app.config import settings


class LLMService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0
        )

    def generate_answer(self, question: str, context: str) -> str:
        prompt = f"""
            You are answering questions using Confluence documentation.

            Use only the context below.
            If the answer is not in the context, say you could not find it.

            Question:
            {question}

            Context:
            {context}
            """

        response = self.llm.invoke(prompt)
        return response.content