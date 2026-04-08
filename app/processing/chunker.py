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
                prefix_parts = [f"Page: {doc.title}"]
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
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:chunk:{chunk_index}",
                        doc_id=doc.doc_id,
                        text=f"Page: {doc.title}\n\n{piece}",
                        title=doc.title,
                        heading_path=[],
                        metadata=doc.metadata,
                    )
                )
                chunk_index += 1

    return chunks