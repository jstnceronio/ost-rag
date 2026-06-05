from dataclasses import dataclass

from langchain_core.documents import Document


@dataclass()
class ChatResult:
    answer: str
    sources: list[dict[str, str | list[str] | None]]


def _build_context(matches: list[Document]) -> str:
    if not matches:
        return "Kein Kontext gefunden."

    context_parts: list[str] = []
    for index, match in enumerate(matches, start=1):
        metadata = match.metadata
        heading_path = metadata.get("heading_path") or []
        heading_text = " > ".join(heading_path) if isinstance(heading_path, list) else ""
        title = str(metadata.get("title") or "Untitled")
        doc_id = str(metadata.get("doc_id") or "")
        chunk_id = str(metadata.get("chunk_id") or "")
        url = str(metadata.get("url") or "")
        chunk_type = str(metadata.get("chunk_type") or "")
        parent_section_id = str(metadata.get("parent_section_id") or "")
        excerpt = str(metadata.get("parent_text") or match.page_content).strip()

        context_parts.append(
            "\n".join(
                [part for part in [
                    f"Source {index}",
                    f"Title: {title}",
                    f"Document ID: {doc_id}",
                    f"Chunk ID: {chunk_id}",
                    f"Parent Section ID: {parent_section_id}" if parent_section_id else "",
                    f"Heading Path: {heading_text}",
                    f"Chunk Type: {chunk_type}" if chunk_type else "",
                    f"URL: {url}" if url else "",
                    f"Content: {excerpt}",
                ] if part]
            )
        )

    return "\n\n".join(context_parts)


def _document_to_source(document: Document) -> dict[str, str | list[str] | None]:
    metadata = document.metadata
    heading_path = metadata.get("heading_path")

    return {
        "title": metadata.get("title"),
        "doc_id": metadata.get("doc_id"),
        "chunk_id": metadata.get("chunk_id"),
        "heading_path": heading_path if isinstance(heading_path, list) else [],
        "url": metadata.get("url"),
        "content": document.page_content.strip(),
    }
