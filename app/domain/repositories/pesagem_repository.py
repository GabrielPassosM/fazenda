import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models.pesagem import Pesagem


class PesagemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, pesagem_id: uuid.UUID) -> Pesagem | None:
        stmt = select(Pesagem).where(Pesagem.id == pesagem_id)
        return self.db.scalar(stmt)

    def create(self, pesagem: Pesagem) -> Pesagem:
        self.db.add(pesagem)
        self.db.flush()
        return pesagem

    def create_many(self, pesagens: list[Pesagem]) -> list[Pesagem]:
        self.db.add_all(pesagens)
        self.db.flush()
        return pesagens

    def delete(self, pesagem: Pesagem) -> None:
        self.db.delete(pesagem)
        self.db.flush()

