from langchain_core.documents import Document

from app.processing.models import Chunk


def chunks_to_documents(chunks: list[Chunk]) -> list[Document]:
    docs: list[Document] = []

    for chunk in chunks:
        docs.append(
            Document(
                page_content=chunk.text,
                metadata={
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "heading_path": chunk.heading_path,
                    **chunk.metadata,
                },
            )
        )

    return docs