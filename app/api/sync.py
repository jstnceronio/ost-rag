from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import limiter, verify_api_key
from app.api.models import SyncRequest, SyncResponse
from app.services.sync_service import run_sync

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
@limiter.limit("5/minute")
def sync(
    request: Request,
    payload: SyncRequest,
    _: None = Depends(verify_api_key),
) -> SyncResponse:
    if not payload.page_id and not payload.space_id:
        raise HTTPException(status_code=400, detail="Page or Space ID required")

    pages, chunks = run_sync(
        space_id=payload.space_id,
        page_id=payload.page_id,
        limit=payload.limit,
    )

    if pages == 0:
        target = payload.page_id or payload.space_id
        raise HTTPException(
            status_code=404,
            detail=f"No pages found in Confluence target '{target}'.",
        )

    return SyncResponse(pages_indexed=pages, chunks_indexed=chunks)
