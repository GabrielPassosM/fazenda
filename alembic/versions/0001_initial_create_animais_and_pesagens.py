"""create pastos, animais and pesagens tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-11-01 22:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pastos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome", name="uq_pastos_nome"),
    )
    op.create_index(op.f("ix_pastos_nome"), "pastos", ["nome"], unique=False)

    op.create_table(
        "animais",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column(
            "fazenda",
            sa.Enum(
                "tiziu",
                "ns_penha",
                name="fazendaenum",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("data_entrada", sa.Date(), nullable=False),
        sa.Column(
            "categoria",
            sa.Enum(
                "bezerro",
                "novilha",
                "vaca",
                "touro",
                name="categoriaanimalenum",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ativo",
                "abatido",
                "morto",
                name="statusanimalenum",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("pasto_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["pasto_id"], ["pastos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fazenda", "numero", name="uq_animais_fazenda_numero"),
    )
    op.create_index(op.f("ix_animais_categoria"), "animais", ["categoria"], unique=False)
    op.create_index(op.f("ix_animais_fazenda"), "animais", ["fazenda"], unique=False)
    op.create_index(op.f("ix_animais_numero"), "animais", ["numero"], unique=False)
    op.create_index(op.f("ix_animais_pasto_id"), "animais", ["pasto_id"], unique=False)
    op.create_index(op.f("ix_animais_status"), "animais", ["status"], unique=False)

    op.create_table(
        "pesagens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("animal_id", sa.Uuid(), nullable=False),
        sa.Column("pasto_id", sa.Uuid(), nullable=True),
        sa.Column("data_pesagem", sa.Date(), nullable=False),
        sa.Column("peso_kg", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["animal_id"], ["animais.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pasto_id"], ["pastos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pesagens_animal_id"), "pesagens", ["animal_id"], unique=False)
    op.create_index(op.f("ix_pesagens_data_pesagem"), "pesagens", ["data_pesagem"], unique=False)
    op.create_index(op.f("ix_pesagens_pasto_id"), "pesagens", ["pasto_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pesagens_pasto_id"), table_name="pesagens")
    op.drop_index(op.f("ix_pesagens_data_pesagem"), table_name="pesagens")
    op.drop_index(op.f("ix_pesagens_animal_id"), table_name="pesagens")
    op.drop_table("pesagens")
    op.drop_index(op.f("ix_animais_status"), table_name="animais")
    op.drop_index(op.f("ix_animais_pasto_id"), table_name="animais")
    op.drop_index(op.f("ix_animais_numero"), table_name="animais")
    op.drop_index(op.f("ix_animais_fazenda"), table_name="animais")
    op.drop_index(op.f("ix_animais_categoria"), table_name="animais")
    op.drop_table("animais")
    op.drop_index(op.f("ix_pastos_nome"), table_name="pastos")
    op.drop_table("pastos")

