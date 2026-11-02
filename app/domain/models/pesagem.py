from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Date, ForeignKey, Numeric, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models.base import Base

if TYPE_CHECKING:
    from app.domain.models.animal import Animal


class Pesagem(Base):
    __tablename__ = "pesagens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("animais.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_pesagem: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    peso_kg: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
    )
    observacao: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    animal: Mapped["Animal"] = relationship(
        "Animal",
        back_populates="pesagens",
    )

