from app.config import settings
from app.embeddings.factory import create_embeddings
from app.processing.mapper import chunks_to_documents
from langchain_community.vectorstores import SupabaseVectorStore
from app.embeddings.supabase_client import get_supabase_client

class IndexingService:
    def __init__(self):
        self.embeddings = create_embeddings()
        self.supabase_client = get_supabase_client()

    def index_chunks(self, chunks: list):
        documents = chunks_to_documents(chunks)

        if not documents:
            raise ValueError("No documents to index")

        vectorstore = SupabaseVectorStore(
            client=self.supabase_client,
            embedding=self.embeddings,
            table_name=settings.supabase_table_name,
            query_name="match_documents",
            chunk_size=100,
        )

        vectorstore.add_documents(documents)

        return vectorstore