import hmac
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.api.models import ChatRequest, ChatResponse, ChatSource, SyncRequest, SyncResponse
from app.services.chat_service import ChatService
from app.services.sync_service import SyncService

"""
Run me locally like this: uvicorn app.api.chat:app --reload
"""

# FastAPI won't automatically reject if header is missing
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str | None = Depends(_api_key_header)) -> None:
    if not key or not hmac.compare_digest(key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

@asynccontextmanager
async def lifespan(api: FastAPI):
    api.state.chat_service = ChatService()
    api.state.sync_service = SyncService()
    yield

app = FastAPI(lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute;300/day")
def chat(request: Request, payload: ChatRequest, _: None = Depends(verify_api_key)) -> ChatResponse:
    chat_service = getattr(request.app.state, "chat_service", None)
    if chat_service is None:
        raise HTTPException(status_code=500, detail="Chat service is not initialized")

    try:
        result = chat_service.answer_question(
            payload.question,
            history=[h.model_dump() for h in payload.history],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return ChatResponse(
        answer=result.answer,
        sources=[ChatSource(**source) for source in result.sources],
    )


@app.post("/sync", response_model=SyncResponse)
def sync(request: Request, payload: SyncRequest, _: None = Depends(verify_api_key)) -> SyncResponse:
    sync_service = getattr(request.app.state, "sync_service", None)
    if sync_service is None:
        raise HTTPException(status_code=500, detail="Sync service is not initialized")

    try:
        result = sync_service.sync(space_id=payload.space_id, limit=payload.limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return SyncResponse(**result)
