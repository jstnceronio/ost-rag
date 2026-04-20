import hmac

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.models import ChatRequest, ChatResponse, ChatSource
from app.services.chat_service import ChatService
from app.config import settings


limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str | None = Depends(_api_key_header)) -> None:
    if not key or not hmac.compare_digest(key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


chat_service: ChatService | None = None


@app.on_event("startup")
def startup_event() -> None:
    global chat_service
    chat_service = ChatService()


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute;300/day")
def chat(
    request: Request,
    payload: ChatRequest,
    _: None = Depends(verify_api_key),
) -> ChatResponse:
    if chat_service is None:
        raise HTTPException(status_code=500, detail="Chat service is not initialized")

    try:
        result = chat_service.answer_question(payload.question)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return ChatResponse(
        answer=result.answer,
        sources=[ChatSource(**source) for source in result.sources],
    )
