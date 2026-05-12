import pytest
from app.processing.chunker import chunk_text, chunk_documents
from app.processing.models import ParsedDocument


def _doc(sections=None, text="short") -> ParsedDocument:
    return ParsedDocument(
        doc_id="doc1",
        title="My Page",
        url=None,
        text=text,
        sections=sections or [],
        metadata={},
    )


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        result = chunk_text("hello world", max_chars=1200)
        assert result == ["hello world"]

    def test_long_text_splits(self):
        text = "a" * 2000
        result = chunk_text(text, max_chars=1000, overlap=100)
        assert len(result) > 1

    def test_overlap_applied(self):
        text = "a" * 1500
        chunks = chunk_text(text, max_chars=1000, overlap=200)
        assert len(chunks[0]) == 1000
        # second chunk starts at offset 800 (1000 - 200)
        assert chunks[1] == text[800:1800]

    def test_exact_length_returns_single_chunk(self):
        text = "x" * 1200
        result = chunk_text(text, max_chars=1200)
        assert result == [text]

    def test_whitespace_normalized(self):
        result = chunk_text("  hello   world  ")
        assert result == ["hello world"]

    def test_empty_string(self):
        result = chunk_text("")
        assert result == [""]


class TestChunkDocuments:
    def test_empty_input(self):
        assert chunk_documents([]) == []

    def test_no_sections_uses_full_text(self):
        doc = _doc(text="Some content here")
        chunks = chunk_documents([doc])
        assert len(chunks) == 1
        assert "Page: My Page" in chunks[0].text
        assert "Some content here" in chunks[0].text

    def test_sections_produce_prefixed_chunks(self):
        doc = _doc(sections=[(["Intro"], "Introduction text"), (["Setup"], "Setup text")])
        chunks = chunk_documents([doc])
        assert len(chunks) == 2
        assert "Section: Intro" in chunks[0].text
        assert "Section: Setup" in chunks[1].text

    def test_chunk_metadata_preserved(self):
        doc = ParsedDocument(
            doc_id="42",
            title="Page",
            url="https://example.com",
            text="content",
            sections=[],
            metadata={"version": 3},
        )
        chunks = chunk_documents([doc])
        assert chunks[0].metadata["version"] == 3

    def test_long_section_splits_into_multiple_chunks(self):
        long_text = "word " * 500  # ~2500 chars
        doc = _doc(sections=[(["Long"], long_text)])
        chunks = chunk_documents([doc])
        assert len(chunks) > 1

    def test_nested_heading_path_in_prefix(self):
        doc = _doc(sections=[(["Top", "Sub"], "nested content")])
        chunks = chunk_documents([doc])
        assert "Top > Sub" in chunks[0].text

    def test_attachment_chunks_include_parent_page_identity(self):
        doc = ParsedDocument(
            doc_id="670171635:attachment:att1",
            title="KI-und-Leistungsnachweise.pdf",
            url="https://example.com/pdf",
            text="",
            sections=[(["Attachment"], "specific PDF content " * 200)],
            metadata={
                "source_type": "attachment",
                "parent_title": "KI und Leistungsnachweise",
                "media_type": "application/pdf",
            },
        )

        chunks = chunk_documents([doc])

        assert len(chunks) > 1
        assert all("Source type: Confluence attachment" in chunk.text for chunk in chunks)
        assert all("Parent page: KI und Leistungsnachweise" in chunk.text for chunk in chunks)
        assert all("Attachment: KI-und-Leistungsnachweise.pdf" in chunk.text for chunk in chunks)
