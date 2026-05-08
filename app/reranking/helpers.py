from langchain_core.documents import Document


def _format_docs(docs: list[Document]) -> str:
    parts = []
    for index, doc in enumerate(docs):
        metadata = doc.metadata
        heading_path = metadata.get("heading_path") or []
        heading_text = " > ".join(heading_path) if isinstance(heading_path, list) else ""

        parts.append(
            "\n".join([
                f"[{index}]",
                f"Title: {metadata.get('title') or 'Untitled'}",
                f"Document ID: {metadata.get('doc_id') or ''}",
                f"Chunk ID: {metadata.get('chunk_id') or ''}",
                f"Heading Path: {heading_text}",
                f"Content: {doc.page_content.strip()}",
            ])
        )

    return "\n\n".join(parts)


def _build_prompt(query: str, docs: list[Document], top_n: int) -> str:
    return f"""
    Frage:
    {query}

    Dokumente:
    {_format_docs(docs)}

    Aufgabe:
    Bewerte jedes Dokument für die Frage und wähle höchstens {top_n} Dokumente aus.

    Bewertung:
    - relevance: Zahl zwischen 0.0 und 1.0.
    - supports_answer: true nur wenn das Dokument konkrete Fakten enthält, die zur Antwort beitragen.
    - reason: sehr kurze Begründung auf Deutsch.

    Antworte ausschließlich als valides JSON in diesem Format:
    {{
      "results": [
        {{"index": 0, "relevance": 0.91, "supports_answer": true, "reason": "enthält die gesuchten Module"}}
      ]
    }}

    Sortiere "results" absteigend nach relevance.
    Wenn kein Dokument die Frage beantwortet, gib "results": [] zurück.
    """.strip()