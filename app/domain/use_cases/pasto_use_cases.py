import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.application.schemas.pasto import PastoCreate, PastoUpdate
from app.domain.models.animal import Animal
from app.domain.models.pasto import Pasto
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.use_cases.exceptions import DomainError, NotFoundError


def create_pasto(db: Session, data: PastoCreate) -> Pasto:
    repo = PastoRepository(db)
    existing = repo.get_by_nome(data.nome)
    if existing is not None:
        raise DomainError(f"Já existe um pasto cadastrado com o nome '{data.nome}'.")

    pasto = Pasto(nome=data.nome)
    repo.create(pasto)
    db.commit()
    db.refresh(pasto)
    return pasto


def update_pasto(db: Session, pasto_id: uuid.UUID, data: PastoUpdate) -> Pasto:
    repo = PastoRepository(db)
    pasto = repo.get_by_id(pasto_id)
    if pasto is None:
        raise NotFoundError("Pasto não encontrado.")

    existing = repo.get_by_nome(data.nome)
    if existing is not None and existing.id != pasto.id:
        raise DomainError(f"Já existe outro pasto com o nome '{data.nome}'.")

    pasto.nome = data.nome
    db.commit()
    db.refresh(pasto)
    return pasto


def delete_pasto(db: Session, pasto_id: uuid.UUID) -> None:
    repo = PastoRepository(db)
    pasto = repo.get_by_id(pasto_id)
    if pasto is None:
        raise NotFoundError("Pasto não encontrado.")

    db.execute(
        update(Animal).where(Animal.pasto_id == pasto.id).values(pasto_id=None)
    )
    repo.delete(pasto)
    db.commit()

