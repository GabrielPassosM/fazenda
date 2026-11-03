from pydantic import BaseModel

from app.application.schemas.animal import (
    AnimalCreate,
    AnimalListItem,
    AnimalLoteCreate,
    AnimalLoteItem,
    AnimalUpdate,
    PaginatedAnimais,
)
from app.application.schemas.pasto import (
    PastoCreate,
    PastoListItem,
    PastoRodizioCreate,
    PastoRodizioResult,
    PastoTransferenciaItem,
    PastoUpdate,
)
from app.application.schemas.pesagem import (
    PesagemCreate,
    PesagemLoteCreate,
    PesagemLoteHistoricoItem,
    PesagemLoteItem,
)


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str


__all__ = [
    "HealthResponse",
    "AnimalCreate",
    "AnimalLoteItem",
    "AnimalLoteCreate",
    "AnimalUpdate",
    "AnimalListItem",
    "PaginatedAnimais",
    "PastoCreate",
    "PastoUpdate",
    "PastoListItem",
    "PastoTransferenciaItem",
    "PastoRodizioCreate",
    "PastoRodizioResult",
    "PesagemCreate",
    "PesagemLoteItem",
    "PesagemLoteCreate",
    "PesagemLoteHistoricoItem",
]
