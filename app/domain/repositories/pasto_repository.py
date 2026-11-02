import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application.schemas.pasto import PastoListItem
from app.domain.models.animal import Animal
from app.domain.models.pasto import Pasto


class PastoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, pasto_id: uuid.UUID) -> Pasto | None:
        stmt = select(Pasto).where(Pasto.id == pasto_id)
        return self.db.scalar(stmt)

    def get_by_nome(self, nome: str) -> Pasto | None:
        stmt = select(Pasto).where(func.lower(Pasto.nome) == nome.strip().lower())
        return self.db.scalar(stmt)

    def list_all(self) -> list[Pasto]:
        stmt = select(Pasto).order_by(Pasto.nome.asc())
        return list(self.db.scalars(stmt).all())

    def list_with_counts(self) -> list[PastoListItem]:
        stmt = (
            select(
                Pasto,
                func.count(Animal.id).label("total_animais"),
            )
            .outerjoin(Animal, Animal.pasto_id == Pasto.id)
            .group_by(Pasto.id)
            .order_by(Pasto.nome.asc())
        )
        rows = self.db.execute(stmt).all()
        return [
            PastoListItem(pasto=row[0], total_animais=row[1])
            for row in rows
        ]

    def create(self, pasto: Pasto) -> Pasto:
        self.db.add(pasto)
        self.db.flush()
        return pasto

    def delete(self, pasto: Pasto) -> None:
        self.db.delete(pasto)
        self.db.flush()

