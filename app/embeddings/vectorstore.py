from pathlib import Path

from langchain_community.vectorstores import FAISS

from app.config import settings
from app.embeddings.factory import create_embeddings


def load_or_create_faiss() -> FAISS:
    embeddings = create_embeddings()
    index_path = Path(settings.faiss_index_path)

    if index_path.exists():
        return FAISS.load_local(
            folder_path=str(index_path),
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
        )

    # Create an empty FAISS store.
    return None