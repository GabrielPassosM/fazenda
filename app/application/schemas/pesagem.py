from datetime import date
from decimal import Decimal
import uuid

from pydantic import BaseModel, Field, field_validator

from app.domain.models.enums import FazendaEnum


class PesagemCreate(BaseModel):
    animal_id: uuid.UUID
    data_pesagem: date
    peso_kg: Decimal = Field(..., gt=0)
    pasto_id: uuid.UUID | None = None
    observacao: str | None = None

    @field_validator("observacao")
    @classmethod
    def clean_observacao(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


class PesagemLoteItem(BaseModel):
    numero: str = Field(..., min_length=1, max_length=50)
    peso_kg: Decimal = Field(..., gt=0)
    pasto_id: uuid.UUID | None = None
    observacao: str | None = None

    @field_validator("numero")
    @classmethod
    def clean_numero(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("O número do animal é obrigatório.")
        return cleaned

    @field_validator("observacao")
    @classmethod
    def clean_observacao(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


class PesagemLoteCreate(BaseModel):
    fazenda: FazendaEnum
    data_pesagem: date
    observacao_padrao: str | None = None
    itens: list[PesagemLoteItem] = Field(..., min_length=1)

    @field_validator("observacao_padrao")
    @classmethod
    def clean_observacao_padrao(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

