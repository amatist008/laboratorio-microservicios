"""Servicio 2 · Productos (catálogo e inventario)."""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Producto
from app.schemas import ProductoActualizar, ProductoCrear, ProductoSalida

PREFIJO = "/productos"

app = FastAPI(
    title="Servicio de Productos",
    version="1.0.0",
    docs_url=f"{PREFIJO}/docs",
    openapi_url=f"{PREFIJO}/openapi.json",
    redoc_url=None,
)
router = APIRouter(prefix=PREFIJO, tags=["productos"])

DB = Annotated[Session, Depends(get_db)]


def _obtener_o_404(db: Session, producto_id: int) -> Producto:
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no encontrado")
    return producto


@router.get("/health")
def health(db: DB) -> dict[str, str]:
    """Liveness + readiness: verifica que la base de datos responda."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Base de datos no disponible"
        ) from exc
    return {"status": "ok", "servicio": "productos"}


@router.get("", response_model=list[ProductoSalida])
def listar_productos(
    db: DB,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    q: Annotated[str | None, Query(max_length=100, description="Filtro por nombre")] = None,
) -> list[Producto]:
    consulta = select(Producto)
    if q:
        # Consulta parametrizada por el ORM: no hay concatenación de SQL.
        consulta = consulta.where(Producto.nombre.ilike(f"%{q}%"))
    consulta = consulta.order_by(Producto.id).offset(skip).limit(limit)
    return list(db.scalars(consulta))


@router.get("/{producto_id}", response_model=ProductoSalida)
def obtener_producto(producto_id: int, db: DB) -> Producto:
    return _obtener_o_404(db, producto_id)


@router.post("", response_model=ProductoSalida, status_code=status.HTTP_201_CREATED)
def crear_producto(datos: ProductoCrear, db: DB) -> Producto:
    producto = Producto(**datos.model_dump())
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.patch("/{producto_id}", response_model=ProductoSalida)
def actualizar_producto(producto_id: int, datos: ProductoActualizar, db: DB) -> Producto:
    producto = _obtener_o_404(db, producto_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(producto, campo, valor)
    db.commit()
    db.refresh(producto)
    return producto


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(producto_id: int, db: DB) -> Response:
    db.delete(_obtener_o_404(db, producto_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


app.include_router(router)
