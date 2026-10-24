from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductoBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=150, examples=["Teclado mecánico"])
    descripcion: str | None = Field(default=None, max_length=2000)
    precio: Decimal = Field(ge=0, max_digits=12, decimal_places=2, examples=["189900.00"])
    stock: int = Field(default=0, ge=0)


class ProductoCrear(ProductoBase):
    pass


class ProductoActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=150)
    descripcion: str | None = Field(default=None, max_length=2000)
    precio: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)


class ProductoSalida(ProductoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creado_en: datetime | None = None
