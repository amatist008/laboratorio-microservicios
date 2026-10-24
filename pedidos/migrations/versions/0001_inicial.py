"""Esquema inicial de pedidos.

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
        "pedidos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("cantidad > 0", name="ck_pedidos_cantidad_positiva"),
    )
    op.create_index("ix_pedidos_usuario_id", "pedidos", ["usuario_id"])
    op.create_index("ix_pedidos_producto_id", "pedidos", ["producto_id"])
    # Semilla coherente con los datos semilla de usuarios (id 1) y productos (id 1, 2)
    op.bulk_insert(
        tabla,
        [
            {
                "usuario_id": 1,
                "producto_id": 1,
                "cantidad": 1,
                "precio_unitario": 189900,
                "total": 189900,
                "estado": "pagado",
            },
            {
                "usuario_id": 1,
                "producto_id": 2,
                "cantidad": 2,
                "precio_unitario": 79900,
                "total": 159800,
                "estado": "pendiente",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_pedidos_producto_id", table_name="pedidos")
    op.drop_index("ix_pedidos_usuario_id", table_name="pedidos")
    op.drop_table("pedidos")
