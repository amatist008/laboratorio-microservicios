"""Conexión a la base de datos propia del servicio (patrón Database-per-Service)."""

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

_opciones_pool = (
    {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
    if DATABASE_URL.startswith("postgresql")
    else {}
)

engine = create_engine(DATABASE_URL, **_opciones_pool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de los modelos ORM."""


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición, cerrada siempre al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
