from dataclasses import dataclass

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


@dataclass
class PastoListItem:
    pasto: Pasto
    total_animais: int = 0

