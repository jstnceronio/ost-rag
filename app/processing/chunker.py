import re

from app.processing.models import ParsedDocument, Chunk

_TARGET_CHILD_TOKENS = 420
_MAX_PARENT_TOKENS = 900
_CHILD_OVERLAP_TOKENS = 80
_MIN_PARENT_TOKENS = 120
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _estimate_tokens(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


def _normalize_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _flatten_text(text: str) -> str:
    return " ".join(text.split())


def _looks_like_atomic_block(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) > 1 and all("|" in line for line in lines):
        return True

    return bool(
        re.match(r"^(```|\s*[-*]\s+|\s*\d+[.)]\s+)", stripped)
        or stripped.lower().startswith(("note:", "warning:", "caution:", "important:"))
    )


def _classify_chunk_type(text: str) -> str:
    stripped = text.strip()
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]

    if stripped.startswith("```"):
        return "code"
    if len(lines) > 1 and all("|" in line for line in lines):
        return "table"
    if any(re.match(r"^\d+[.)]\s+", line) for line in lines):
        return "procedure"
    if any(re.match(r"^[-*]\s+", line) for line in lines):
        return "list"
    return "section"

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

        sections = _build_parent_sections(doc)
        for parent_index, parent in enumerate(sections):
            prefix_parts = _prefix_parts(doc)
            heading_path = parent["heading_path"]
            if heading_path:
                prefix_parts.append(f"Section: {' > '.join(heading_path)}")
            prefix = "\n".join(prefix_parts) + "\n\n"

            parent_text = parent["text"]
            parent_context = prefix + parent_text
            for child_index, piece in enumerate(_split_child_chunks(parent_text)):
                chunk_type = _classify_chunk_type(piece)
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:chunk:{chunk_index}",
                        doc_id=doc.doc_id,
                        text=prefix + piece,
                        title=doc.title,
                        heading_path=heading_path,
                        metadata={
                            **doc.metadata,
                            "chunk_type": chunk_type,
                            "parent_section_id": f"{doc.doc_id}:section:{parent_index}",
                            "parent_section_index": parent_index,
                            "parent_heading_path": heading_path,
                            "parent_text": parent_context,
                            "child_index": child_index,
                        },
                    )
                )
                chunk_index += 1

    return chunks


def _build_parent_sections(doc: ParsedDocument) -> list[dict]:
    if not doc.sections:
        text = _normalize_text(doc.text)
        return [{"heading_path": [], "text": text}] if text else []

    parents: list[dict] = []
    current_heading: list[str] | None = None
    current_blocks: list[str] = []

    for heading_path, raw_text in doc.sections:
        block = _normalize_text(raw_text)
        if not block:
            continue

        block_tokens = _estimate_tokens(block)
        current_text = "\n\n".join(current_blocks)
        current_tokens = _estimate_tokens(current_text)
        heading_changed = current_heading is not None and heading_path != current_heading
        oversized = (
            current_blocks
            and current_tokens + block_tokens > _MAX_PARENT_TOKENS
            and current_tokens >= _MIN_PARENT_TOKENS
            and not _looks_like_atomic_block(block)
        )

        if heading_changed or oversized:
            parents.append(
                {
                    "heading_path": current_heading or [],
                    "text": "\n\n".join(current_blocks),
                }
            )
            current_blocks = []

        current_heading = heading_path
        current_blocks.append(block)

    if current_blocks:
        parents.append(
            {
                "heading_path": current_heading or [],
                "text": "\n\n".join(current_blocks),
            }
        )

    return parents


def _split_child_chunks(text: str) -> list[str]:
    text = _normalize_text(text)
    if _estimate_tokens(text) <= _TARGET_CHILD_TOKENS:
        return [text]

    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if len(blocks) > 1:
        return _split_blocks_into_child_chunks(blocks)

    return _split_words_with_overlap(_flatten_text(text))


def _split_blocks_into_child_chunks(blocks: list[str]) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []

    for block in blocks:
        block_tokens = _estimate_tokens(block)
        current_text = "\n\n".join(current)
        current_tokens = _estimate_tokens(current_text)

        if block_tokens > _TARGET_CHILD_TOKENS and not _looks_like_atomic_block(block):
            if current:
                chunks.append(current_text)
                current = []
            chunks.extend(_split_words_with_overlap(_flatten_text(block)))
            continue

        if current and current_tokens + block_tokens > _TARGET_CHILD_TOKENS:
            chunks.append(current_text)
            current = []

        current.append(block)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _split_words_with_overlap(text: str) -> list[str]:
    words = text.split()
    if len(words) <= _TARGET_CHILD_TOKENS:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max(1, _TARGET_CHILD_TOKENS - _CHILD_OVERLAP_TOKENS)
    while start < len(words):
        end = min(len(words), start + _TARGET_CHILD_TOKENS)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
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
