import asyncio
import logging
from datetime import datetime, timedelta

from app.confluence.client import ConfluenceClient
from app.embeddings.indexing import IndexingService
from app.processing.models import ParsedDocument
from app.processing.normalize import parse_confluence_page
from app.processing.chunker import chunk_documents
from app.config import settings

logger = logging.getLogger(__name__)


def run_sync(space_id: str, limit: int | None = None) -> tuple[int, int]:
    client = ConfluenceClient(
        base_url=settings.confluence_base_url,
        api_token=settings.confluence_api_key,
    )
    pages = client.get_pages_by_space_id(space_id=space_id, limit=limit)
    documents: list[ParsedDocument] = [parse_confluence_page(page) for page in pages]
    chunks = chunk_documents(documents)
    IndexingService().index_chunks(chunks)
    return len(documents), len(chunks)


async def start_daily_sync(space_id: str, hour: int = 6) -> None:
    while True:
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logger.info("Next sync at %s (in %.0fs)", next_run.isoformat(), wait_seconds)
        await asyncio.sleep(wait_seconds)

        try:
            pages, chunks = await asyncio.to_thread(run_sync, space_id)
            logger.info("Daily sync complete: %d pages, %d chunks", pages, chunks)
        except Exception:
            logger.exception("Daily sync failed")
