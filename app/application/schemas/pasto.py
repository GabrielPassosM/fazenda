from dataclasses import dataclass
import uuid

from pydantic import BaseModel, Field, field_validator

from app.domain.models.pasto import Pasto


class PastoCreate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)

    @field_validator("nome")
    @classmethod
    def clean_nome(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("O nome do pasto é obrigatório.")
        return cleaned


class PastoUpdate(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)

    @field_validator("nome")
    @classmethod
    def clean_nome(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("O nome do pasto é obrigatório.")
        return cleaned


class PastoTransferenciaItem(BaseModel):
    pasto_origem_id: uuid.UUID
    pasto_destino_id: uuid.UUID


class PastoRodizioCreate(BaseModel):
    etapas: list[PastoTransferenciaItem] = Field(..., min_length=1)


@dataclass
class PastoRodizioResult:
    total_animais_movidos: int
    resumo_etapas: list[str]


@dataclass
class PastoListItem:
    pasto: Pasto
    total_animais: int = 0


