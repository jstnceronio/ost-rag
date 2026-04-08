from langchain_community.vectorstores import FAISS
from langchain_core.vectorstores import VectorStoreRetriever

from app.config import settings
from app.embeddings.factory import create_embeddings


class RetrieverService:
    def __init__(self):
        self.embeddings = create_embeddings()

    def get_retriever(self) -> VectorStoreRetriever:
        vectorstore = FAISS.load_local(
            folder_path=settings.faiss_index_path,
            embeddings=self.embeddings,
            allow_dangerous_deserialization=True,
        )
        return vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5},
        )