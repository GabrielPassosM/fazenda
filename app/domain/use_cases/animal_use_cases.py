import uuid

from sqlalchemy.orm import Session

from app.application.schemas.animal import (
    AnimalCreate,
    AnimalLoteCreate,
    AnimalUpdate,
)
from app.domain.models.animal import Animal
from app.domain.models.enums import CategoriaAnimalEnum, StatusAnimalEnum
from app.domain.models.pesagem import Pesagem
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.repositories.pasto_repository import PastoRepository
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

    if data.pasto_id is not None:
        pasto_repo = PastoRepository(db)
        if pasto_repo.get_by_id(data.pasto_id) is None:
            raise NotFoundError("Pasto não encontrado.")

    animal = Animal(
        numero=data.numero,
        fazenda=data.fazenda,
        data_entrada=data.data_entrada,
        categoria=data.categoria,
        status=data.status,
        observacoes=data.observacoes,
        pasto_id=data.pasto_id,
    )
    animal_repo.create(animal)

    if data.peso_inicial_kg is not None:
        pesagem = Pesagem(
            animal_id=animal.id,
            pasto_id=animal.pasto_id,
            data_pesagem=data.data_pesagem_inicial or data.data_entrada,
            peso_kg=data.peso_inicial_kg,
            observacao=data.observacao_pesagem,
        )
        pesagem_repo.create(pesagem)

    db.commit()
    db.refresh(animal)
    return animal


def create_animais_em_lote(db: Session, data: AnimalLoteCreate) -> list[Animal]:
    animal_repo = AnimalRepository(db)
    pesagem_repo = PesagemRepository(db)

    seen_numeros: set[str] = set()
    duplicados_lote: list[str] = []
    for item in data.itens:
        if item.numero in seen_numeros and item.numero not in duplicados_lote:
            duplicados_lote.append(item.numero)
        seen_numeros.add(item.numero)

    if duplicados_lote:
        dup_str = ", ".join(f"'{n}'" for n in duplicados_lote)
        raise DomainError(
            f"Número(s) repetido(s) no mesmo lote: {dup_str}."
        )

    numeros = [item.numero for item in data.itens]
    existing_map = animal_repo.get_by_fazenda_and_numeros(data.fazenda, numeros)

    existing_numeros: list[str] = []
    for item in data.itens:
        if item.numero in existing_map and item.numero not in existing_numeros:
            existing_numeros.append(item.numero)

    if existing_numeros:
        numeros_str = ", ".join(f"'{n}'" for n in existing_numeros)
        raise DomainError(
            f"Já existe(m) animal(is) cadastrado(s) na fazenda {data.fazenda.label} com o(s) número(s): {numeros_str}."
        )

    animais_to_create: list[Animal] = []
    for item in data.itens:
        animais_to_create.append(
            Animal(
                numero=item.numero,
                fazenda=data.fazenda,
                data_entrada=data.data,
                categoria=CategoriaAnimalEnum.VACA,
                status=StatusAnimalEnum.ATIVO,
            )
        )

    animal_repo.create_many(animais_to_create)

    lote_id = uuid.uuid4()
    pesagens_to_create: list[Pesagem] = []
    for animal, item in zip(animais_to_create, data.itens, strict=True):
        pesagens_to_create.append(
            Pesagem(
                animal_id=animal.id,
                data_pesagem=data.data,
                peso_kg=item.peso_kg,
                em_lote=True,
                lote_id=lote_id,
            )
        )

    pesagem_repo.create_many(pesagens_to_create)
    db.commit()
    return animais_to_create


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

    if data.pasto_id is not None:
        pasto_repo = PastoRepository(db)
        if pasto_repo.get_by_id(data.pasto_id) is None:
            raise NotFoundError("Pasto não encontrado.")

    animal.numero = data.numero
    animal.fazenda = data.fazenda
    animal.data_entrada = data.data_entrada
    animal.categoria = data.categoria
    animal.status = data.status
    animal.observacoes = data.observacoes
    animal.pasto_id = data.pasto_id

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

