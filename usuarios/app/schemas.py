from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioBase(BaseModel):
    nombre: str = Field(min_length=2, max_length=120, examples=["Ana Gómez"])
    email: EmailStr = Field(examples=["ana@example.com"])


class UsuarioCrear(UsuarioBase):
    pass


class UsuarioActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None


class UsuarioSalida(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creado_en: datetime | None = None
