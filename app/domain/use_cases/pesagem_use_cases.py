import uuid

from sqlalchemy.orm import Session

from app.application.schemas.pesagem import PesagemCreate, PesagemLoteCreate
from app.domain.models.pesagem import Pesagem
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.repositories.pesagem_repository import PesagemRepository
from app.domain.use_cases.exceptions import DomainError, NotFoundError


def create_pesagem_individual(db: Session, data: PesagemCreate) -> Pesagem:
    animal_repo = AnimalRepository(db)
    pesagem_repo = PesagemRepository(db)

    animal = animal_repo.get_by_id(data.animal_id)
    if animal is None:
        raise NotFoundError("Animal não encontrado.")

    pasto_id = (
        data.pasto_id
        if "pasto_id" in data.model_fields_set
        else animal.pasto_id
    )
    if pasto_id is not None:
        pasto_repo = PastoRepository(db)
        if pasto_repo.get_by_id(pasto_id) is None:
            raise NotFoundError("Pasto não encontrado.")

    pesagem = Pesagem(
        animal_id=animal.id,
        pasto_id=pasto_id,
        data_pesagem=data.data_pesagem,
        peso_kg=data.peso_kg,
        observacao=data.observacao,
    )
    pesagem_repo.create(pesagem)
    db.commit()
    db.refresh(pesagem)
    return pesagem


def create_pesagens_em_lote(db: Session, data: PesagemLoteCreate) -> list[Pesagem]:
    animal_repo = AnimalRepository(db)
    pesagem_repo = PesagemRepository(db)
    pasto_repo = PastoRepository(db)

    numeros = [item.numero for item in data.itens]
    animais_map = animal_repo.get_by_fazenda_and_numeros(data.fazenda, numeros)

    missing_numeros: list[str] = []
    for item in data.itens:
        if item.numero not in animais_map and item.numero not in missing_numeros:
            missing_numeros.append(item.numero)

    if missing_numeros:
        numeros_str = ", ".join(f"'{n}'" for n in missing_numeros)
        raise DomainError(
            f"Animal(is) não encontrado(s) na fazenda {data.fazenda.label}: {numeros_str}."
        )

    pesagens_to_create: list[Pesagem] = []
    for item in data.itens:
        animal = animais_map[item.numero]
        pasto_id = (
            item.pasto_id
            if "pasto_id" in item.model_fields_set
            else animal.pasto_id
        )
        if pasto_id is not None and pasto_repo.get_by_id(pasto_id) is None:
            raise DomainError("Pasto selecionado não encontrado.")

        obs = item.observacao if item.observacao else data.observacao_padrao
        pesagens_to_create.append(
            Pesagem(
                animal_id=animal.id,
                pasto_id=pasto_id,
                data_pesagem=data.data_pesagem,
                peso_kg=item.peso_kg,
                observacao=obs,
            )
        )

    pesagem_repo.create_many(pesagens_to_create)
    db.commit()
    return pesagens_to_create


def delete_pesagem(db: Session, pesagem_id: uuid.UUID) -> uuid.UUID:
    pesagem_repo = PesagemRepository(db)
    pesagem = pesagem_repo.get_by_id(pesagem_id)
    if pesagem is None:
        raise NotFoundError("Pesagem não encontrada.")

    animal_id = pesagem.animal_id
    pesagem_repo.delete(pesagem)
    db.commit()
    return animal_id

