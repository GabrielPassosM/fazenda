from decimal import Decimal, ROUND_HALF_UP
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.application.schemas.pesagem import PesagemLoteHistoricoItem
from app.domain.models.animal import Animal
from app.domain.models.pesagem import Pesagem


class PesagemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, pesagem_id: uuid.UUID) -> Pesagem | None:
        stmt = select(Pesagem).where(Pesagem.id == pesagem_id)
        return self.db.scalar(stmt)

    def list_historico_lotes(self) -> list[PesagemLoteHistoricoItem]:
        obs_padrao_col = func.coalesce(
            Pesagem.observacao_lote,
            case((Pesagem.lote_id.is_(None), Pesagem.observacao), else_=None),
        ).label("observacao_padrao")

        stmt = (
            select(
                Animal.fazenda,
                Pesagem.data_pesagem,
                func.count(Pesagem.id).label("quantidade_animais"),
                func.avg(Pesagem.peso_kg).label("peso_medio_kg"),
                obs_padrao_col,
            )
            .join(Animal, Animal.id == Pesagem.animal_id)
            .where(Pesagem.em_lote.is_(True))
            .group_by(
                Pesagem.lote_id,
                Animal.fazenda,
                Pesagem.data_pesagem,
                obs_padrao_col,
            )
            .order_by(
                Pesagem.data_pesagem.desc(),
                Animal.fazenda.asc(),
            )
        )

        rows = self.db.execute(stmt).all()
        return [
            PesagemLoteHistoricoItem(
                fazenda=row[0],
                data_pesagem=row[1],
                quantidade_animais=int(row[2]),
                peso_medio_kg=Decimal(str(row[3])).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                observacao_padrao=row[4],
            )
            for row in rows
        ]

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


