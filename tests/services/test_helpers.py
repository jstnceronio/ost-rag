import pytest
from langchain_core.documents import Document
from app.services.helpers import _build_context, _document_to_source


def _doc(content="text", **meta) -> Document:
    return Document(page_content=content, metadata=meta)


class TestBuildContext:
    def test_empty_matches_returns_fallback(self):
        result = _build_context([])
        assert "Kein Kontext" in result

    def test_single_match_numbered(self):
        doc = _doc("some content", title="Page", doc_id="1", chunk_id="1:0", heading_path=[])
        result = _build_context([doc])
        assert "Source 1" in result
        assert "some content" in result

    def test_multiple_matches_numbered(self):
        docs = [_doc(f"content {i}", title="P", doc_id=str(i), chunk_id=f"{i}:0", heading_path=[]) for i in range(3)]
        result = _build_context(docs)
        assert "Source 1" in result
        assert "Source 2" in result
        assert "Source 3" in result

    def test_heading_path_joined(self):
        doc = _doc("text", title="P", doc_id="1", chunk_id="1:0", heading_path=["A", "B", "C"])
        result = _build_context([doc])
        assert "A > B > C" in result

    def test_missing_title_defaults_to_untitled(self):
        doc = _doc("text", doc_id="1", chunk_id="1:0", heading_path=[])
        result = _build_context([doc])
        assert "Untitled" in result


class TestDocumentToSource:
    def test_all_fields_returned(self):
        doc = _doc("text", title="T", doc_id="1", chunk_id="1:0", heading_path=["A"], url="https://x.com")
        source = _document_to_source(doc)
        assert source["title"] == "T"
        assert source["doc_id"] == "1"
        assert source["chunk_id"] == "1:0"
        assert source["heading_path"] == ["A"]
        assert source["url"] == "https://x.com"

    def test_missing_heading_path_returns_empty_list(self):
        doc = _doc("text", title="T", doc_id="1", chunk_id="1:0")
        source = _document_to_source(doc)
        assert source["heading_path"] == []

    def test_non_list_heading_path_returns_empty_list(self):
        doc = _doc("text", title="T", doc_id="1", chunk_id="1:0", heading_path="not-a-list")
        source = _document_to_source(doc)
        assert source["heading_path"] == []
