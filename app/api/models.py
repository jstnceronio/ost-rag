from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=500)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="The user's question")
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=10,
        description="Previous conversation turns, oldest first",
    )


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
    space_id: str = Field(default="720898", description="Confluence space ID to sync")
    limit: int = Field(default=5, ge=1, description="Maximum number of pages to fetch")


class SyncResponse(BaseModel):
    space_id: str
    pages_fetched: int
    documents_parsed: int
    chunks_indexed: int
