from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="The user's question")

class ChatSource(BaseModel):
    title: str | None
    doc_id: str | None
    chunk_id: str | None
    heading_path: list[str] = Field(default_factory=list)
    url: str | None

class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)

