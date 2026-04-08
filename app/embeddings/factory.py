from langchain_openai import OpenAIEmbeddings

from app.config import settings


def create_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
    )