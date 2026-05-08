from app.processing.models import ParsedDocument, Chunk

def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks

def chunk_documents(parsed_docs: list[ParsedDocument]) -> list[Chunk]:
    chunks: list[Chunk] = []

    for doc in parsed_docs:
        chunk_index = 0

        if doc.sections:
            for heading_path, section_text in doc.sections:
                prefix_parts = _prefix_parts(doc)
                if heading_path:
                    prefix_parts.append(f"Section: {' > '.join(heading_path)}")
                prefix = "\n".join(prefix_parts) + "\n\n"

                for piece in chunk_text(section_text):
                    chunks.append(
                        Chunk(
                            chunk_id=f"{doc.doc_id}:chunk:{chunk_index}",
                            doc_id=doc.doc_id,
                            text=prefix + piece,
                            title=doc.title,
                            heading_path=heading_path,
                            metadata=doc.metadata,
                        )
                    )
                    chunk_index += 1
        else:
            for piece in chunk_text(doc.text):
                prefix = "\n".join(_prefix_parts(doc)) + "\n\n"
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:chunk:{chunk_index}",
                        doc_id=doc.doc_id,
                        text=prefix + piece,
                        title=doc.title,
                        heading_path=[],
                        metadata=doc.metadata,
                    )
                )
                chunk_index += 1

    return chunks


def _prefix_parts(doc: ParsedDocument) -> list[str]:
    if doc.metadata.get("source_type") == "attachment":
        prefix_parts = ["Source type: Confluence attachment"]
        parent_title = doc.metadata.get("parent_title")
        if parent_title:
            prefix_parts.append(f"Parent page: {parent_title}")
        prefix_parts.append(f"Attachment: {doc.title}")
        media_type = doc.metadata.get("media_type")
        if media_type:
            prefix_parts.append(f"Media type: {media_type}")
        return prefix_parts

    return [f"Page: {doc.title}"]
