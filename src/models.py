from pydantic import BaseModel, Field
from typing import List, Optional, Dict


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
    """
    Caso del golden dataset de evals.

    `expected_chunk_ids` y `hard_negative_chunk_ids` están indexados por
    estrategia de chunking ("structural" / "fixed") porque cada chunker
    trocea el corpus con límites distintos: un mismo hecho puede vivir en
    IDs de chunk diferentes según la estrategia. Mantenerlos separados
    permite aplicar la MISMA fórmula de precision/recall a ambas
    estrategias (ver evals/runner.py), en vez de comparar métricas
    calculadas con criterios distintos.
    """
    id: str
    question: str
    is_out_of_scope: bool = False
    is_cross_document: bool = False
    is_hard_negative_case: bool = False
    expected_chunk_ids: Dict[str, List[str]] = Field(default_factory=lambda: {"structural": [], "fixed": []})
    hard_negative_chunk_ids: Dict[str, List[str]] = Field(default_factory=lambda: {"structural": [], "fixed": []})