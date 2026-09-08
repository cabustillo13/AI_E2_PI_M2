from pydantic import BaseModel, Field
from typing import List, Literal


class TicketRequest(BaseModel):
    ticket: str = Field(..., description="El texto libre de la consulta del usuario entrante.")


class TicketResponse(BaseModel):
    category: Literal["billing", "technical", "account", "other"] = Field(
        ..., description="Categoría principal del ticket."
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Nivel de confianza de la clasificación."
    )
    answer: str = Field(..., description="Respuesta sugerida para el usuario.")
    actions: List[str] = Field(
        default_factory=list, description="Lista de acciones sugeridas para el agente humano."
    )


class JudgeResponse(BaseModel):
    corrected_category: Literal["billing", "technical", "account", "other"] = Field(...)
    feedback: str = Field(..., description="Justificación del juez sobre la categoría.")