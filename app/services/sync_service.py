import logging

from app.confluence.client import ConfluenceClient
from app.embeddings.indexing import IndexingService
from app.processing.models import ParsedDocument
from app.processing.attachments import parse_confluence_attachment
from app.processing.normalize import parse_confluence_page
from app.processing.chunker import chunk_documents
from app.config import settings

logger = logging.getLogger(__name__)


def run_sync(space_id: str | None = None, page_id: str | None = None, limit: int | None = None) -> tuple[int, int]:
    if not space_id and not page_id:
        raise ValueError("Either space_id or page_id is required")

    client = ConfluenceClient(
        base_url=settings.confluence_base_url,
        api_token=settings.confluence_api_key,
    )

    if page_id:
        pages = client.get_page_tree(page_id=page_id, limit=limit)
    else:
        pages = client.get_pages_by_space_id(space_id=space_id or "", limit=limit)

    if not pages:
        return 0, 0

    documents: list[ParsedDocument] = [parse_confluence_page(page) for page in pages]
    attachments = client.get_attachments_for_pages(pages)
    documents.extend(
        doc
        for attachment in attachments
        if (doc := parse_confluence_attachment(attachment)) is not None
    )

    chunks = chunk_documents(documents)
    if not chunks:
        return len(pages), 0

    IndexingService().index_chunks(chunks)
    return len(pages), len(chunks)
