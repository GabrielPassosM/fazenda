from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import uuid

from pydantic import BaseModel, Field, field_validator

from app.domain.models.animal import Animal
from app.domain.models.enums import CategoriaAnimalEnum, FazendaEnum, StatusAnimalEnum


class AnimalCreate(BaseModel):
    numero: str = Field(..., min_length=1, max_length=50)
    fazenda: FazendaEnum
    data_entrada: date
    categoria: CategoriaAnimalEnum
    status: StatusAnimalEnum = StatusAnimalEnum.ATIVO
    observacoes: str | None = None
    pasto_id: uuid.UUID | None = None

    peso_inicial_kg: Decimal | None = None
    data_pesagem_inicial: date | None = None
    observacao_pesagem: str | None = None

    @field_validator("numero")
    @classmethod
    def clean_numero(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("O número do animal é obrigatório.")
        return cleaned

    @field_validator("observacoes", "observacao_pesagem")
    @classmethod
    def clean_optional_str(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None

    @field_validator("peso_inicial_kg")
    @classmethod
    def validate_peso_positivo(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("O peso deve ser maior que zero.")
        return v


class AnimalUpdate(BaseModel):
    numero: str = Field(..., min_length=1, max_length=50)
    fazenda: FazendaEnum
    data_entrada: date
    categoria: CategoriaAnimalEnum
    status: StatusAnimalEnum
    observacoes: str | None = None
    pasto_id: uuid.UUID | None = None

    @field_validator("numero")
    @classmethod
    def clean_numero(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("O número do animal é obrigatório.")
        return cleaned

    @field_validator("observacoes")
    @classmethod
    def clean_optional_str(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned if cleaned else None


class AnimalLoteItem(BaseModel):
    numero: str = Field(..., min_length=1, max_length=50)
    peso_kg: Decimal = Field(..., gt=0)

    @field_validator("numero")
    @classmethod
    def clean_numero(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("O número do animal é obrigatório.")
        return cleaned


class AnimalLoteCreate(BaseModel):
    fazenda: FazendaEnum
    data: date
    itens: list[AnimalLoteItem] = Field(..., min_length=1)


@dataclass
class AnimalListItem:
    animal: Animal
    ultimo_peso_kg: Decimal | None = None
    ultima_data_pesagem: date | None = None


@dataclass
class PaginatedAnimais:
    items: list[AnimalListItem]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

