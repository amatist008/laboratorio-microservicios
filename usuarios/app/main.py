"""Servicio 1 · Usuarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario
from app.schemas import UsuarioActualizar, UsuarioCrear, UsuarioSalida

PREFIJO = "/usuarios"

app = FastAPI(
    title="Servicio de Usuarios",
    version="1.0.0",
    docs_url=f"{PREFIJO}/docs",
    openapi_url=f"{PREFIJO}/openapi.json",
    redoc_url=None,
)
router = APIRouter(prefix=PREFIJO, tags=["usuarios"])

DB = Annotated[Session, Depends(get_db)]


def _obtener_o_404(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return usuario


def _confirmar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El email ya está registrado") from exc


@router.get("/health")
def health(db: DB) -> dict[str, str]:
    """Liveness + readiness: verifica que la base de datos responda."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Base de datos no disponible"
        ) from exc
    return {"status": "ok", "servicio": "usuarios"}


@router.get("", response_model=list[UsuarioSalida])
def listar_usuarios(
    db: DB,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Usuario]:
    consulta = select(Usuario).order_by(Usuario.id).offset(skip).limit(limit)
    return list(db.scalars(consulta))


@router.get("/{usuario_id}", response_model=UsuarioSalida)
def obtener_usuario(usuario_id: int, db: DB) -> Usuario:
    return _obtener_o_404(db, usuario_id)


@router.post("", response_model=UsuarioSalida, status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCrear, db: DB) -> Usuario:
    usuario = Usuario(**datos.model_dump())
    db.add(usuario)
    _confirmar(db)
    db.refresh(usuario)
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioSalida)
def actualizar_usuario(usuario_id: int, datos: UsuarioActualizar, db: DB) -> Usuario:
    usuario = _obtener_o_404(db, usuario_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)
    _confirmar(db)
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(usuario_id: int, db: DB) -> Response:
    db.delete(_obtener_o_404(db, usuario_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


app.include_router(router)
