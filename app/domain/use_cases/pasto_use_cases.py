import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.application.schemas.pasto import (
    PastoCreate,
    PastoRodizioCreate,
    PastoRodizioResult,
    PastoUpdate,
)
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


def rodar_pastos(db: Session, data: PastoRodizioCreate) -> PastoRodizioResult:
    repo = PastoRepository(db)

    seen_origens: set[uuid.UUID] = set()
    snapshots: list[tuple[Pasto, Pasto, list[uuid.UUID]]] = []

    for idx, etapa in enumerate(data.etapas, start=1):
        if etapa.pasto_origem_id == etapa.pasto_destino_id:
            raise DomainError(
                f"Etapa {idx}: o pasto de destino deve ser diferente do pasto de origem."
            )

        if etapa.pasto_origem_id in seen_origens:
            raise DomainError(
                "O mesmo pasto de origem não pode ser transferido mais de uma vez no mesmo rodízio."
            )
        seen_origens.add(etapa.pasto_origem_id)

        origem = repo.get_by_id(etapa.pasto_origem_id)
        if origem is None:
            raise NotFoundError("Pasto de origem não encontrado.")

        destino = repo.get_by_id(etapa.pasto_destino_id)
        if destino is None:
            raise NotFoundError("Pasto de destino não encontrado.")

        animal_ids = repo.get_animal_ids_by_pasto(origem.id)
        if not animal_ids:
            raise DomainError(
                f"O pasto '{origem.nome}' não possui animais alocados para transferir."
            )

        snapshots.append((origem, destino, animal_ids))

    total_movidos = 0
    resumo_etapas: list[str] = []

    for origem, destino, animal_ids in snapshots:
        db.execute(
            update(Animal)
            .where(Animal.id.in_(animal_ids))
            .values(pasto_id=destino.id)
        )
        qtd = len(animal_ids)
        total_movidos += qtd
        label = "animal" if qtd == 1 else "animais"
        resumo_etapas.append(f"{qtd} {label} de '{origem.nome}' → '{destino.nome}'")

    db.commit()
    return PastoRodizioResult(
        total_animais_movidos=total_movidos,
        resumo_etapas=resumo_etapas,
    )


