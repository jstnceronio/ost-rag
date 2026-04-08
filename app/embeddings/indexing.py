from pathlib import Path

from langchain_community.vectorstores import FAISS

from app.config import settings
from app.embeddings.factory import create_embeddings
from app.processing.mapper import chunks_to_documents


class IndexingService:
    def __init__(self):
        self.embeddings = create_embeddings()

    def index_chunks(self, chunks: list) -> FAISS:
        documents = chunks_to_documents(chunks)

        if not documents:
            raise ValueError("No documents to index")

        index_path = Path(settings.faiss_index_path)

        if index_path.exists():
            vectorstore = FAISS.load_local(
                folder_path=str(index_path),
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True,
            )
            vectorstore.add_documents(documents)
        else:
            vectorstore = FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings,
            )

        vectorstore.save_local(str(index_path))
        return vectorstore