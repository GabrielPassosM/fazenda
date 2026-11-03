from typing import TYPE_CHECKING
import uuid

from sqlalchemy import String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.animal import Animal
    from app.domain.models.pesagem import Pesagem


class Pasto(Base):
    __tablename__ = "pastos"
    __table_args__ = (
        UniqueConstraint("nome", name="uq_pastos_nome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    animais: Mapped[list["Animal"]] = relationship(
        "Animal",
        back_populates="pasto",
    )
    pesagens: Mapped[list["Pesagem"]] = relationship(
        "Pesagem",
        back_populates="pasto",
    )

