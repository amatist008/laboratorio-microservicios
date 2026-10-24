"""Servicio 3 · Pedidos."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.clientes import ClienteServicios, ServicioNoDisponibleError, get_clientes
from app.database import get_db
from app.models import Pedido
from app.schemas import EstadoPedido, PedidoCambioEstado, PedidoCrear, PedidoSalida

PREFIJO = "/pedidos"

app = FastAPI(
    title="Servicio de Pedidos",
    version="1.0.0",
    docs_url=f"{PREFIJO}/docs",
    openapi_url=f"{PREFIJO}/openapi.json",
    redoc_url=None,
)
router = APIRouter(prefix=PREFIJO, tags=["pedidos"])

DB = Annotated[Session, Depends(get_db)]
Clientes = Annotated[ClienteServicios, Depends(get_clientes)]

# Máquina de estados: transiciones permitidas
TRANSICIONES: dict[EstadoPedido, set[EstadoPedido]] = {
    EstadoPedido.PENDIENTE: {EstadoPedido.PAGADO, EstadoPedido.CANCELADO},
    EstadoPedido.PAGADO: {EstadoPedido.ENVIADO, EstadoPedido.CANCELADO},
    EstadoPedido.ENVIADO: set(),
    EstadoPedido.CANCELADO: set(),
}


def _obtener_o_404(db: Session, pedido_id: int) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if pedido is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return pedido


@router.get("/health")
def health(db: DB) -> dict[str, str]:
    """Liveness + readiness: verifica que la base de datos responda."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Base de datos no disponible"
        ) from exc
    return {"status": "ok", "servicio": "pedidos"}


@router.get("", response_model=list[PedidoSalida])
def listar_pedidos(
    db: DB,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    usuario_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[Pedido]:
    consulta = select(Pedido)
    if usuario_id is not None:
        consulta = consulta.where(Pedido.usuario_id == usuario_id)
    consulta = consulta.order_by(Pedido.id).offset(skip).limit(limit)
    return list(db.scalars(consulta))


@router.get("/{pedido_id}", response_model=PedidoSalida)
def obtener_pedido(pedido_id: int, db: DB) -> Pedido:
    return _obtener_o_404(db, pedido_id)


@router.post("", response_model=PedidoSalida, status_code=status.HTTP_201_CREATED)
def crear_pedido(datos: PedidoCrear, db: DB, clientes: Clientes) -> Pedido:
    try:
        usuario = clientes.obtener_usuario(datos.usuario_id)
        producto = clientes.obtener_producto(datos.producto_id)
    except ServicioNoDisponibleError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Servicio dependiente no disponible"
        ) from exc

    if usuario is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El usuario no existe")
    if producto is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El producto no existe")
    if int(producto["stock"]) < datos.cantidad:
        raise HTTPException(status.HTTP_409_CONFLICT, "Stock insuficiente")

    precio = Decimal(str(producto["precio"]))
    pedido = Pedido(
        usuario_id=datos.usuario_id,
        producto_id=datos.producto_id,
        cantidad=datos.cantidad,
        precio_unitario=precio,
        total=precio * datos.cantidad,
        estado=EstadoPedido.PENDIENTE.value,
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return pedido


@router.patch("/{pedido_id}/estado", response_model=PedidoSalida)
def cambiar_estado(pedido_id: int, datos: PedidoCambioEstado, db: DB) -> Pedido:
    pedido = _obtener_o_404(db, pedido_id)
    actual = EstadoPedido(pedido.estado)
    if datos.estado not in TRANSICIONES[actual]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Transición no permitida: {actual.value} -> {datos.estado.value}",
        )
    pedido.estado = datos.estado.value
    db.commit()
    db.refresh(pedido)
    return pedido


app.include_router(router)
