import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.deps import limiter, verify_api_key
from app.api.models import ChatRequest, ChatResponse, ChatSource
from app.services.chat_service import ChatService
from app.services.sync_service import start_daily_sync

from app.api import sync as sync_module
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.chat_service = ChatService()
    task = asyncio.create_task(
        start_daily_sync(settings.confluence_space_id, hour=settings.sync_hour)
    )
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(sync_module.router)


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
