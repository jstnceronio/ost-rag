from typing import List

from app.config import settings
from app.confluence.client import ConfluenceClient
from app.embeddings.indexing import IndexingService
from app.processing.chunker import chunk_documents
from app.processing.models import ParsedDocument
from app.processing.normalize import parse_confluence_page

DEFAULT_SPACE_ID = "720898"
DEFAULT_PAGE_LIMIT = 500


class SyncService:
    def __init__(self):
        self.client = ConfluenceClient(
            base_url=settings.confluence_base_url,
            api_token=settings.confluence_api_key,
        )
        self.indexing_service = IndexingService()

    def sync(self, space_id: str = DEFAULT_SPACE_ID, limit: int = DEFAULT_PAGE_LIMIT) -> dict[str, int | str]:
        pages = self.client.get_pages_by_space_id(space_id=space_id, limit=limit)
        documents: List[ParsedDocument] = [parse_confluence_page(page) for page in pages]
        chunks = chunk_documents(documents)

        self.indexing_service.index_chunks(chunks)

        return {
            "space_id": space_id,
            "pages_fetched": len(pages),
            "documents_parsed": len(documents),
            "chunks_indexed": len(chunks),
        }
