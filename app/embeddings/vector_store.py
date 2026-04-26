from pathlib import Path

from langchain_community.vectorstores import FAISS, SupabaseVectorStore

from app.config import settings
from app.embeddings.supabase_client import get_supabase_client


def create_vector_store(embedding, documents: list | None = None):
    provider = settings.vector_store_provider.lower()

    if provider == "supabase":
        # use the remote embedding storage
        return SupabaseVectorStore(
            client=get_supabase_client(),
            embedding=embedding,
            table_name=settings.supabase_table_name,
            query_name="match_documents",
            chunk_size=100,
        )

    if provider == "faiss":
        index_path = Path(settings.faiss_index_path).resolve()

        if documents is not None:
            if index_path.exists():
                # load the existing store
                vector_store = FAISS.load_local(
                    str(index_path),
                    embedding,
                    allow_dangerous_deserialization=True,
                )
                # append documents to the index
                vector_store.add_documents(documents)
            else:
                # create a new data dir
                index_path.mkdir(parents=True, exist_ok=True)
                vector_store = FAISS.from_documents(documents, embedding)

            # persist index on disk
            vector_store.save_local(str(index_path))
            return vector_store

        if not index_path.exists():
            raise ValueError(f"No FAISS index found at {index_path} :0 - are you sure the path is correct?")

        return FAISS.load_local(
            str(index_path),
            embedding,
            allow_dangerous_deserialization=True,
        )

    raise ValueError(f"For the vector_store_provider, choose between 'supabase' or 'faiss': {settings.vector_store_provider}")
