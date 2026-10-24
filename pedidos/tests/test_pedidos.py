from decimal import Decimal

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.clientes import ClienteServicios, ServicioNoDisponibleError, get_clientes
from app.database import get_db
from app.main import app

USUARIOS = {1: {"id": 1, "nombre": "Ana", "email": "ana@example.com"}}
PRODUCTOS = {
    1: {"id": 1, "nombre": "Teclado", "precio": "189900.00", "stock": 5},
    2: {"id": 2, "nombre": "Mouse", "precio": "79900.50", "stock": 0},
}


class ClientesFalsos:
    """Doble de prueba: simula las APIs de usuarios y productos."""

    caido = False

    def obtener_usuario(self, usuario_id):
        if self.caido:
            raise ServicioNoDisponibleError("usuarios caído")
        return USUARIOS.get(usuario_id)

    def obtener_producto(self, producto_id):
        return PRODUCTOS.get(producto_id)


@pytest.fixture
def falsos(client):
    dobles = ClientesFalsos()
    app.dependency_overrides[get_clientes] = lambda: dobles
    return dobles


def _crear(client, usuario_id=1, producto_id=1, cantidad=2):
    return client.post(
        "/pedidos",
        json={"usuario_id": usuario_id, "producto_id": producto_id, "cantidad": cantidad},
    )


# --------------------------------------------------------------- endpoints
def test_health_ok(client):
    assert client.get("/pedidos/health").json()["servicio"] == "pedidos"


def test_health_bd_caida_responde_503(client):
    class SesionRota:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("sin conexión"))

    app.dependency_overrides[get_db] = lambda: SesionRota()
    assert client.get("/pedidos/health").status_code == 503


def test_crear_calcula_total(client, falsos):
    r = _crear(client, cantidad=2)
    assert r.status_code == 201
    cuerpo = r.json()
    assert Decimal(cuerpo["total"]) == Decimal("379800.00")
    assert cuerpo["estado"] == "pendiente"


def test_usuario_inexistente_422(client, falsos):
    r = _crear(client, usuario_id=99)
    assert r.status_code == 422
    assert "usuario" in r.json()["detail"]


def test_producto_inexistente_422(client, falsos):
    assert _crear(client, producto_id=99).status_code == 422


def test_stock_insuficiente_409(client, falsos):
    assert _crear(client, producto_id=2, cantidad=1).status_code == 409


def test_servicio_dependiente_caido_503(client, falsos):
    falsos.caido = True
    assert _crear(client).status_code == 503


def test_cantidad_cero_422(client, falsos):
    assert _crear(client, cantidad=0).status_code == 422


def test_listar_y_filtrar_por_usuario(client, falsos):
    _crear(client)
    _crear(client, cantidad=1)
    assert len(client.get("/pedidos").json()) == 2
    assert client.get("/pedidos", params={"usuario_id": 7}).json() == []
    assert len(client.get("/pedidos", params={"usuario_id": 1}).json()) == 2


def test_obtener_y_404(client, falsos):
    pid = _crear(client).json()["id"]
    assert client.get(f"/pedidos/{pid}").status_code == 200
    assert client.get("/pedidos/999").status_code == 404


def test_flujo_de_estados_valido(client, falsos):
    pid = _crear(client).json()["id"]
    for estado in ("pagado", "enviado"):
        r = client.patch(f"/pedidos/{pid}/estado", json={"estado": estado})
        assert r.status_code == 200
        assert r.json()["estado"] == estado


def test_transicion_invalida_409(client, falsos):
    pid = _crear(client).json()["id"]
    r = client.patch(f"/pedidos/{pid}/estado", json={"estado": "enviado"})
    assert r.status_code == 409


def test_estado_desconocido_422(client, falsos):
    pid = _crear(client).json()["id"]
    r = client.patch(f"/pedidos/{pid}/estado", json={"estado": "perdido"})
    assert r.status_code == 422


# --------------------------------------------------------------- cliente HTTP
def _cliente_con(manejador):
    """Cliente real con transporte simulado: no hay red, pero sí todo el código HTTP."""
    return ClienteServicios(
        "http://usuarios:8000/", "http://productos:8000", transport=httpx.MockTransport(manejador)
    )


def test_cliente_respuesta_ok():
    cliente = _cliente_con(lambda req: httpx.Response(200, json={"id": 1}))
    assert cliente.obtener_usuario(1) == {"id": 1}
    assert cliente.obtener_producto(1) == {"id": 1}


def test_cliente_404_devuelve_none():
    cliente = _cliente_con(lambda req: httpx.Response(404))
    assert cliente.obtener_usuario(1) is None


def test_cliente_500_lanza_error():
    cliente = _cliente_con(lambda req: httpx.Response(500))
    with pytest.raises(ServicioNoDisponibleError):
        cliente.obtener_producto(1)


def test_cliente_error_de_red_lanza_error():
    def caido(req):
        raise httpx.ConnectError("sin ruta", request=req)

    cliente = _cliente_con(caido)
    with pytest.raises(ServicioNoDisponibleError):
        cliente.obtener_usuario(1)


def test_get_clientes_lee_entorno(monkeypatch):
    monkeypatch.setenv("USUARIOS_URL", "http://u:1")
    monkeypatch.setenv("PRODUCTOS_URL", "http://p:2")
    get_clientes.cache_clear()
    c = get_clientes()
    get_clientes.cache_clear()
    assert (c.usuarios_url, c.productos_url) == ("http://u:1", "http://p:2")


def test_get_clientes_reutiliza_instancia():
    get_clientes.cache_clear()
    assert get_clientes() is get_clientes()
    get_clientes.cache_clear()
