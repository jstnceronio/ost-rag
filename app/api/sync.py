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
    pages, chunks = run_sync(space_id=payload.space_id, limit=payload.limit)

    if pages == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No pages found in Confluence space '{payload.space_id}'.",
        )

    return SyncResponse(pages_indexed=pages, chunks_indexed=chunks)
