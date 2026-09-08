from pydantic import BaseModel, Field
from typing import List, Optional


class ChunkRelated(BaseModel):
    chunk_id: str
    source: str
    header: Optional[str] = None
    content: str
    score: float


class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=3, ge=1, le=10)
    enable_rerank: bool = False


class RAGQueryResponse(BaseModel):
    user_question: str
    system_answer: str
    chunks_related: List[ChunkRelated]
    latency_seconds: float
    estimated_cost_usd: float


class GoldenTestCase(BaseModel):
    id: str
    question: str
    expected_chunk_ids: List[str]
    is_out_of_scope: bool = False