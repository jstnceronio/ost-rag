from fastapi import FastAPI, HTTPException

from app.api.models import ChatRequest, ChatResponse, ChatSource
from app.services.chat_service import ChatService


app = FastAPI()
chat_service: ChatService | None = None


@app.on_event("startup")
def startup_event() -> None:
    global chat_service
    chat_service = ChatService()

@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
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
