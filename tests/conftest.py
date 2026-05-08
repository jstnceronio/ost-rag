from datetime import datetime
import pytest
from app.confluence.models import ConfluenceAttachment, ConfluencePage
from app.processing.models import ParsedDocument, Chunk
from langchain_core.documents import Document


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.api.deps import limiter
    limiter._storage.reset()
    yield


def make_confluence_page(**kwargs) -> ConfluencePage:
    defaults = dict(
        id="123",
        title="Test Page",
        space_id="SPACE1",
        parent_id=None,
        status="current",
        url="https://wiki.example.com/pages/123",
        body_storage="<p>Hello world</p>",
        version=1,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 6, 1),
    )
    return ConfluencePage(**{**defaults, **kwargs})


def make_confluence_attachment(**kwargs) -> ConfluenceAttachment:
    defaults = dict(
        id="att1",
        title="notes.txt",
        page_id="123",
        page_title="Test Page",
        media_type="text/plain",
        file_size=11,
        url="https://wiki.example.com/download/attachments/123/notes.txt",
        download_url="https://wiki.example.com/download/attachments/123/notes.txt?api=v2",
        version=1,
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 6, 1),
        content=b"Hello world",
    )
    return ConfluenceAttachment(**{**defaults, **kwargs})


def make_parsed_document(**kwargs) -> ParsedDocument:
    defaults = dict(
        doc_id="123",
        title="Test Page",
        url="https://wiki.example.com/pages/123",
        text="Test content",
        sections=[],
        metadata={"version": 1, "url": "https://wiki.example.com/pages/123"},
    )
    return ParsedDocument(**{**defaults, **kwargs})


def make_chunk(**kwargs) -> Chunk:
    defaults = dict(
        chunk_id="123:chunk:0",
        doc_id="123",
        text="Page: Test\n\nSome text",
        title="Test",
        heading_path=[],
        metadata={},
    )
    return Chunk(**{**defaults, **kwargs})


def make_document(**kwargs) -> Document:
    metadata = kwargs.pop("metadata", {"doc_id": "123", "title": "Test", "chunk_id": "123:chunk:0", "heading_path": []})
    content = kwargs.pop("content", "Some content")
    return Document(page_content=content, metadata=metadata)
