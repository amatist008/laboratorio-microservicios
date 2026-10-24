from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Pedido(Base):
    """Un pedido referencia usuario y producto SOLO por id.

    No hay llaves foráneas hacia otras bases de datos: la integridad referencial
    entre servicios se valida por API en el momento de crear el pedido.
    """

    __tablename__ = "pedidos"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_pedidos_cantidad_positiva"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, index=True)
    producto_id: Mapped[int] = mapped_column(Integer, index=True)
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
