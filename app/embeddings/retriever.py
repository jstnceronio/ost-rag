from langchain_core.vectorstores import VectorStoreRetriever

from app.embeddings.factory import create_embeddings
from app.embeddings.vector_store import create_vector_store


class RetrieverService:
    def __init__(self):
        self.embeddings = create_embeddings()

    def get_retriever(self) -> VectorStoreRetriever:
        vectorstore = create_vector_store(self.embeddings)

        return vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 20},
        )
