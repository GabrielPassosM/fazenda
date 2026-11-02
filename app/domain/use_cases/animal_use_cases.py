import uuid

from sqlalchemy.orm import Session

from app.application.schemas.animal import AnimalCreate, AnimalUpdate
from app.domain.models.animal import Animal
from app.domain.models.pesagem import Pesagem
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.repositories.pesagem_repository import PesagemRepository
from app.domain.use_cases.exceptions import DomainError, NotFoundError


def create_animal(db: Session, data: AnimalCreate) -> Animal:
    animal_repo = AnimalRepository(db)
    pesagem_repo = PesagemRepository(db)

    existing = animal_repo.get_by_fazenda_and_numero(data.fazenda, data.numero)
    if existing is not None:
        raise DomainError(
            f"Já existe um animal cadastrado com o número '{data.numero}' na fazenda {data.fazenda.label}."
        )

    animal = Animal(
        numero=data.numero,
        fazenda=data.fazenda,
        data_entrada=data.data_entrada,
        categoria=data.categoria,
        status=data.status,
        observacoes=data.observacoes,
    )
    animal_repo.create(animal)

    if data.peso_inicial_kg is not None:
        pesagem = Pesagem(
            animal_id=animal.id,
            data_pesagem=data.data_pesagem_inicial or data.data_entrada,
            peso_kg=data.peso_inicial_kg,
            observacao=data.observacao_pesagem,
        )
        pesagem_repo.create(pesagem)

    db.commit()
    db.refresh(animal)
    return animal


def update_animal(db: Session, animal_id: uuid.UUID, data: AnimalUpdate) -> Animal:
    animal_repo = AnimalRepository(db)
    animal = animal_repo.get_by_id(animal_id)
    if animal is None:
        raise NotFoundError("Animal não encontrado.")

    existing = animal_repo.get_by_fazenda_and_numero(data.fazenda, data.numero)
    if existing is not None and existing.id != animal.id:
        raise DomainError(
            f"Já existe outro animal com o número '{data.numero}' na fazenda {data.fazenda.label}."
        )

    animal.numero = data.numero
    animal.fazenda = data.fazenda
    animal.data_entrada = data.data_entrada
    animal.categoria = data.categoria
    animal.status = data.status
    animal.observacoes = data.observacoes

    db.commit()
    db.refresh(animal)
    return animal


def delete_animal(db: Session, animal_id: uuid.UUID) -> None:
    animal_repo = AnimalRepository(db)
    animal = animal_repo.get_by_id(animal_id)
    if animal is None:
        raise NotFoundError("Animal não encontrado.")

    animal_repo.delete(animal)
    db.commit()

