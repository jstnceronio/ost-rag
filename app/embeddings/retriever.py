from langchain_core.vectorstores import VectorStoreRetriever
from langchain_community.vectorstores import SupabaseVectorStore
from app.embeddings.supabase_client import get_supabase_client

from app.config import settings
from app.embeddings.factory import create_embeddings


class RetrieverService:
    def __init__(self):
        self.embeddings = create_embeddings()
        self.supabase_client = get_supabase_client()

    def get_retriever(self) -> VectorStoreRetriever:
        vectorstore = SupabaseVectorStore(
            client=self.supabase_client,
            embedding=self.embeddings,
            table_name=settings.supabase_table_name,
            query_name="match_documents",
        )

        return vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5},
        )