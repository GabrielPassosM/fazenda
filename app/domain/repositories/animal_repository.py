from decimal import Decimal
import math
import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.application.schemas.animal import AnimalListItem, PaginatedAnimais
from app.domain.models.animal import Animal
from app.domain.models.enums import (
    CategoriaAnimalEnum,
    FazendaEnum,
    OrdenacaoAnimalEnum,
    StatusAnimalEnum,
)
from app.domain.models.pesagem import Pesagem


class AnimalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, animal_id: uuid.UUID) -> Animal | None:
        stmt = (
            select(Animal)
            .options(
                selectinload(Animal.pesagens).selectinload(Pesagem.pasto),
                selectinload(Animal.pasto),
            )
            .where(Animal.id == animal_id)
        )
        return self.db.scalar(stmt)

    def get_by_fazenda_and_numero(
        self, fazenda: FazendaEnum, numero: str
    ) -> Animal | None:
        stmt = (
            select(Animal)
            .options(selectinload(Animal.pasto))
            .where(
                Animal.fazenda == fazenda,
                Animal.numero == numero.strip(),
            )
        )
        return self.db.scalar(stmt)

    def get_by_fazenda_and_numeros(
        self, fazenda: FazendaEnum, numeros: list[str]
    ) -> dict[str, Animal]:
        cleaned = [n.strip() for n in numeros if n.strip()]
        if not cleaned:
            return {}
        stmt = select(Animal).where(
            Animal.fazenda == fazenda,
            Animal.numero.in_(cleaned),
        )
        animais = self.db.scalars(stmt).all()
        return {a.numero: a for a in animais}

    def count_ativos(self) -> int:
        stmt = select(func.count(Animal.id)).where(
            Animal.status == StatusAnimalEnum.ATIVO
        )
        return self.db.scalar(stmt) or 0

    def list_paginated(
        self,
        page: int = 1,
        page_size: int = 15,
        q: str | None = None,
        fazenda: FazendaEnum | None = None,
        categoria: CategoriaAnimalEnum | None = None,
        status: StatusAnimalEnum | None = None,
        pasto_id: uuid.UUID | None = None,
        peso_min: Decimal | None = None,
        peso_max: Decimal | None = None,
        ordenar_por: OrdenacaoAnimalEnum = OrdenacaoAnimalEnum.DATA_ENTRADA_DESC,
    ) -> PaginatedAnimais:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))

        rn = (
            func.row_number()
            .over(
                partition_by=Pesagem.animal_id,
                order_by=(Pesagem.data_pesagem.desc(), Pesagem.id.desc()),
            )
            .label("rn")
        )
        latest_pesagem_subq = select(
            Pesagem.animal_id,
            Pesagem.peso_kg.label("ultimo_peso_kg"),
            Pesagem.data_pesagem.label("ultima_data_pesagem"),
            rn,
        ).subquery()

        filters = []
        if q and q.strip():
            filters.append(Animal.numero.ilike(f"%{q.strip()}%"))
        if fazenda:
            filters.append(Animal.fazenda == fazenda)
        if categoria:
            filters.append(Animal.categoria == categoria)
        if status:
            filters.append(Animal.status == status)
        if pasto_id:
            filters.append(Animal.pasto_id == pasto_id)
        if peso_min is not None:
            filters.append(latest_pesagem_subq.c.ultimo_peso_kg >= peso_min)
        if peso_max is not None:
            filters.append(latest_pesagem_subq.c.ultimo_peso_kg <= peso_max)

        count_stmt = select(func.count(Animal.id)).outerjoin(
            latest_pesagem_subq,
            and_(
                Animal.id == latest_pesagem_subq.c.animal_id,
                latest_pesagem_subq.c.rn == 1,
            ),
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = self.db.scalar(count_stmt) or 0
        total_pages = max(1, math.ceil(total / page_size))
        if page > total_pages:
            page = total_pages

        order_by_map = {
            OrdenacaoAnimalEnum.DATA_ENTRADA_DESC: (
                Animal.data_entrada.desc(),
                Animal.numero.asc(),
            ),
            OrdenacaoAnimalEnum.DATA_ENTRADA_ASC: (
                Animal.data_entrada.asc(),
                Animal.numero.asc(),
            ),
            OrdenacaoAnimalEnum.PESO_DESC: (
                latest_pesagem_subq.c.ultimo_peso_kg.desc().nulls_last(),
                Animal.numero.asc(),
            ),
            OrdenacaoAnimalEnum.PESO_ASC: (
                latest_pesagem_subq.c.ultimo_peso_kg.asc().nulls_last(),
                Animal.numero.asc(),
            ),
        }
        order_clauses = order_by_map.get(
            ordenar_por, order_by_map[OrdenacaoAnimalEnum.DATA_ENTRADA_DESC]
        )

        stmt = (
            select(
                Animal,
                latest_pesagem_subq.c.ultimo_peso_kg,
                latest_pesagem_subq.c.ultima_data_pesagem,
            )
            .options(selectinload(Animal.pasto))
            .outerjoin(
                latest_pesagem_subq,
                and_(
                    Animal.id == latest_pesagem_subq.c.animal_id,
                    latest_pesagem_subq.c.rn == 1,
                ),
            )
            .order_by(*order_clauses)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if filters:
            stmt = stmt.where(*filters)

        rows = self.db.execute(stmt).all()
        items = [
            AnimalListItem(
                animal=row[0],
                ultimo_peso_kg=row[1],
                ultima_data_pesagem=row[2],
            )
            for row in rows
        ]

        return PaginatedAnimais(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def create(self, animal: Animal) -> Animal:
        self.db.add(animal)
        self.db.flush()
        return animal

    def delete(self, animal: Animal) -> None:
        self.db.delete(animal)
        self.db.flush()

