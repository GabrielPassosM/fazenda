from pydantic import BaseModel

from app.application.schemas.animal import (
    AnimalCreate,
    AnimalListItem,
    AnimalUpdate,
    PaginatedAnimais,
)
from app.application.schemas.pesagem import (
    PesagemCreate,
    PesagemLoteCreate,
    PesagemLoteItem,
)


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str


__all__ = [
    "HealthResponse",
    "AnimalCreate",
    "AnimalUpdate",
    "AnimalListItem",
    "PaginatedAnimais",
    "PesagemCreate",
    "PesagemLoteItem",
    "PesagemLoteCreate",
]
