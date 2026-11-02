from datetime import date
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.models.base import Base
from app.domain.models.enums import CategoriaAnimalEnum, FazendaEnum, StatusAnimalEnum

if TYPE_CHECKING:
    from app.domain.models.pasto import Pasto
    from app.domain.models.pesagem import Pesagem


def _enum_values(enum_cls: type) -> list[str]:
    return [e.value for e in enum_cls]


class Animal(Base):
    __tablename__ = "animais"
    __table_args__ = (
        UniqueConstraint("fazenda", "numero", name="uq_animais_fazenda_numero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    numero: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    fazenda: Mapped[FazendaEnum] = mapped_column(
        SAEnum(
            FazendaEnum,
            native_enum=False,
            length=30,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    data_entrada: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    categoria: Mapped[CategoriaAnimalEnum] = mapped_column(
        SAEnum(
            CategoriaAnimalEnum,
            native_enum=False,
            length=30,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[StatusAnimalEnum] = mapped_column(
        SAEnum(
            StatusAnimalEnum,
            native_enum=False,
            length=30,
            values_callable=_enum_values,
            validate_strings=True,
        ),
        nullable=False,
        default=StatusAnimalEnum.ATIVO,
        index=True,
    )
    observacoes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    pasto_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("pastos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    pasto: Mapped["Pasto | None"] = relationship(
        "Pasto",
        back_populates="animais",
    )
    pesagens: Mapped[list["Pesagem"]] = relationship(
        "Pesagem",
        back_populates="animal",
        cascade="all, delete-orphan",
        order_by="desc(Pesagem.data_pesagem), desc(Pesagem.id)",
    )
