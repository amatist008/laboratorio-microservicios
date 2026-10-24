from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EstadoPedido(StrEnum):
    PENDIENTE = "pendiente"
    PAGADO = "pagado"
    ENVIADO = "enviado"
    CANCELADO = "cancelado"


class PedidoCrear(BaseModel):
    usuario_id: int = Field(gt=0)
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=1000)


class PedidoCambioEstado(BaseModel):
    estado: EstadoPedido


class PedidoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    producto_id: int
    cantidad: int
    precio_unitario: Decimal
    total: Decimal
    estado: EstadoPedido
    creado_en: datetime | None = None
