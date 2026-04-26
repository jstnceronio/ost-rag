from app.embeddings.factory import create_embeddings
from app.processing.mapper import chunks_to_documents
from app.embeddings.vector_store import create_vector_store

class IndexingService:
    def __init__(self):
        self.embeddings = create_embeddings()

    def index_chunks(self, chunks: list):
        documents = chunks_to_documents(chunks)

        if not documents:
            raise ValueError("No documents to index")

        return create_vector_store(self.embeddings, documents=documents)
