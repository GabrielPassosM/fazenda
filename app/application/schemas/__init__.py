"""Schemas e DTOs Pydantic da camada de aplicação."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str

