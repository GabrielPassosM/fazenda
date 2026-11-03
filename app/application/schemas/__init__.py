from pydantic import BaseModel

from app.application.schemas.animal import (
    AnimalCreate,
    AnimalListItem,
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
    "PastoCreate",
    "PastoUpdate",
    "PastoListItem",
    "PastoTransferenciaItem",
    "PastoRodizioCreate",
    "PastoRodizioResult",
    "PesagemCreate",
    "PesagemLoteItem",
    "PesagemLoteCreate",
]
