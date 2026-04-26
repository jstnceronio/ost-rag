import sys
from pathlib import Path

"""
A script to retrieve the test chunks from Confluence for debugging and analysing them.
Run me with: uv run scripts/test_retrieval.py
"""

# for the 'app' import
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from app.embeddings.retriever import RetrieverService


def _shorten(text: str, max_chars: int = 400) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."

TEST_QUERY = "Was sind die ersten 6 Schritte mit meinem neuen Ost Account?"


def main() -> int:

    retriever = RetrieverService().get_retriever()
    matches = retriever.invoke(TEST_QUERY)

    print("=" * 80)
    print(f"Query: {TEST_QUERY}")
    print(f"Matches: {len(matches)}")
    print("=" * 80)

    if not matches:
        print("No chunks found.")
        return 0

    for index, match in enumerate(matches, start=1):
        metadata = match.metadata
        heading_path = metadata.get("heading_path") or []
        heading_text = " > ".join(heading_path) if isinstance(heading_path, list) else ""

        print(f"[{index}] Title: {metadata.get('title') or 'Untitled'}")
        print(f"    Doc ID: {metadata.get('doc_id') or '-'}")
        print(f"    Chunk ID: {metadata.get('chunk_id') or '-'}")
        print(f"    URL: {metadata.get('url') or '-'}")
        print(f"    Heading Path: {heading_text or '-'}")
        print(f"    Content: {_shorten(match.page_content)}")
        print("-" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
