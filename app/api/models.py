from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=500)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=10)


class ChatSource(BaseModel):
    title: str | None
    doc_id: str | None
    chunk_id: str | None
    heading_path: list[str] = Field(default_factory=list)
    url: str | None


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)


class SyncRequest(BaseModel):
    space_id: str | None = None
    page_id: str | None = None
    limit: int | None = Field(default=None, gt=0)


class SyncResponse(BaseModel):
    pages_indexed: int
    chunks_indexed: int
