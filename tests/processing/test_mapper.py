from app.processing.mapper import chunks_to_documents
from app.processing.models import Chunk


def _chunk(**kwargs) -> Chunk:
    defaults = dict(
        chunk_id="doc1:chunk:0",
        doc_id="doc1",
        text="Page: Test\n\nSome text",
        title="Test",
        heading_path=["Intro"],
        metadata={"version": 1, "url": "https://example.com"},
    )
    return Chunk(**{**defaults, **kwargs})


class TestChunksToDocuments:
    def test_page_content_is_chunk_text(self):
        docs = chunks_to_documents([_chunk(text="Hello")])
        assert docs[0].page_content == "Hello"

    def test_chunk_id_in_metadata(self):
        docs = chunks_to_documents([_chunk(chunk_id="abc:chunk:5")])
        assert docs[0].metadata["chunk_id"] == "abc:chunk:5"

    def test_doc_id_in_metadata(self):
        docs = chunks_to_documents([_chunk(doc_id="xyz")])
        assert docs[0].metadata["doc_id"] == "xyz"

    def test_title_in_metadata(self):
        docs = chunks_to_documents([_chunk(title="My Page")])
        assert docs[0].metadata["title"] == "My Page"

    def test_heading_path_in_metadata(self):
        docs = chunks_to_documents([_chunk(heading_path=["A", "B"])])
        assert docs[0].metadata["heading_path"] == ["A", "B"]

    def test_extra_metadata_merged(self):
        docs = chunks_to_documents([_chunk(metadata={"version": 3, "url": "https://x.com"})])
        assert docs[0].metadata["version"] == 3
        assert docs[0].metadata["url"] == "https://x.com"

    def test_empty_list_returns_empty(self):
        assert chunks_to_documents([]) == []

    def test_multiple_chunks(self):
        chunks = [_chunk(chunk_id=f"doc:chunk:{i}", text=f"text {i}") for i in range(3)]
        docs = chunks_to_documents(chunks)
        assert len(docs) == 3
        assert docs[2].page_content == "text 2"

    def test_strips_nul_characters_from_content_and_metadata(self):
        docs = chunks_to_documents([
            _chunk(
                text="Hello\x00 world",
                title="Bad\x00 title",
                heading_path=["Intro\x00"],
                metadata={
                    "url": "https://example.com/\x00bad",
                    "nested": {"value": "keep\x00going"},
                    "items": ["one\x00", "two"],
                },
            )
        ])

        assert docs[0].page_content == "Hello world"
        assert docs[0].metadata["title"] == "Bad title"
        assert docs[0].metadata["heading_path"] == ["Intro"]
        assert docs[0].metadata["url"] == "https://example.com/bad"
        assert docs[0].metadata["nested"]["value"] == "keepgoing"
        assert docs[0].metadata["items"] == ["one", "two"]
