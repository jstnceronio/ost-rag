import logging
from pathlib import Path

from langchain_community.vectorstores import FAISS, SupabaseVectorStore
from postgrest.exceptions import APIError

from app.config import settings
from app.embeddings.supabase_client import get_supabase_client

_UPSERT_BATCH_SIZE = 20

logger = logging.getLogger(__name__)

def create_vector_store(embedding, documents: list | None = None):
    provider = settings.vector_store_provider.lower()

    if provider == "supabase":
        # use the remote embedding storage
        client = get_supabase_client()

        if documents:
            for i in range(0, len(documents), _UPSERT_BATCH_SIZE):
                batch = documents[i : i + _UPSERT_BATCH_SIZE]
                texts = [doc.page_content for doc in batch]
                vectors = embedding.embed_documents(texts)

                rows = [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "embedding": vector,
                    }
                    for doc, vector in zip(batch, vectors)
                ]

                _upsert_rows(client, rows)

                print(f"  Upserted {min(i + _UPSERT_BATCH_SIZE, len(documents))}/{len(documents)} chunks...")

        return SupabaseVectorStore(
            client=client,
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


def _upsert_rows(client, rows: list[dict]) -> None:
    """Upsert rows, isolating only chunks rejected for unsupported Postgres text."""
    try:
        client.table(settings.supabase_table_name).upsert(
            rows,
            on_conflict="chunk_id",
        ).execute()
    except APIError as error:
        if not _is_unsupported_text_error(error):
            raise

        if len(rows) == 1:
            chunk_id = rows[0].get("metadata", {}).get("chunk_id")
            logger.warning("Skipping chunk %s after Supabase rejected text payload: %s", chunk_id, error)
            return

        mid = len(rows) // 2
        _upsert_rows(client, rows[:mid])
        _upsert_rows(client, rows[mid:])


def _is_unsupported_text_error(error: APIError) -> bool:
    """Return true for PostgREST errors caused by values Postgres cannot store as text."""
    return (
        getattr(error, "code", None) == "22P05"
        or "unsupported Unicode escape sequence" in str(error)
        or "\\u0000 cannot be converted to text" in str(error)
    )
