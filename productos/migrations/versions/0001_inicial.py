"""Esquema inicial de productos con datos semilla.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    tabla = op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("precio >= 0", name="ck_productos_precio_no_negativo"),
        sa.CheckConstraint("stock >= 0", name="ck_productos_stock_no_negativo"),
    )
    op.create_index("ix_productos_nombre", "productos", ["nombre"])
    op.bulk_insert(
        tabla,
        [
            {
                "nombre": "Teclado mecánico",
                "descripcion": "Switches rojos",
                "precio": 189900,
                "stock": 25,
            },
            {"nombre": "Mouse inalámbrico", "descripcion": "2.4 GHz", "precio": 79900, "stock": 40},
            {
                "nombre": "Monitor 24 pulgadas",
                "descripcion": "IPS 75 Hz",
                "precio": 649900,
                "stock": 10,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_productos_nombre", table_name="productos")
    op.drop_table("productos")
