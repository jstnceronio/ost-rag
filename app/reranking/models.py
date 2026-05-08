from pydantic import BaseModel, Field


class RerankResult(BaseModel):
    index: int
    relevance: float = Field(ge=0.0, le=1.0)
    supports_answer: bool
    reason: str


class RerankResponse(BaseModel):
    results: list[RerankResult]
