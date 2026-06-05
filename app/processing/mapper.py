from typing import Any

from langchain_core.documents import Document

from app.processing.models import Chunk


def chunks_to_documents(chunks: list[Chunk]) -> list[Document]:
    docs: list[Document] = []

    for chunk in chunks:
        docs.append(
            Document(
                page_content=_strip_nul(chunk.text),
                metadata={
                    "chunk_id": _strip_nul(chunk.chunk_id),
                    "doc_id": _strip_nul(chunk.doc_id),
                    "title": _strip_nul(chunk.title),
                    "heading_path": _strip_nul(chunk.heading_path),
                    **_strip_nul(chunk.metadata),
                },
            )
        )

    return docs


def _strip_nul(value: Any) -> Any:
    """Remove NUL characters recursively because Postgres text/jsonb cannot store them."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_strip_nul(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_nul(item) for item in value)
    if isinstance(value, dict):
        return {
            _strip_nul(key): _strip_nul(item)
            for key, item in value.items()
        }
    return value
