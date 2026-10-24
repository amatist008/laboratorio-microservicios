from decimal import Decimal

from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app

TECLADO = {"nombre": "Teclado", "descripcion": "Mecánico", "precio": "189900.00", "stock": 5}


def _crear(client, **cambios):
    return client.post("/productos", json={**TECLADO, **cambios})


def test_health_ok(client):
    r = client.get("/productos/health")
    assert r.status_code == 200
    assert r.json()["servicio"] == "productos"


def test_health_bd_caida_responde_503(client):
    class SesionRota:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("sin conexión"))

    app.dependency_overrides[get_db] = lambda: SesionRota()
    assert client.get("/productos/health").status_code == 503


def test_crear_y_obtener(client):
    r = _crear(client)
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.get(f"/productos/{pid}")
    assert r.status_code == 200
    assert Decimal(r.json()["precio"]) == Decimal("189900.00")
    assert r.json()["stock"] == 5


def test_listar_y_filtrar(client):
    _crear(client, nombre="Teclado mecánico")
    _crear(client, nombre="Mouse óptico")
    assert len(client.get("/productos").json()) == 2
    filtrados = client.get("/productos", params={"q": "mouse"}).json()
    assert [p["nombre"] for p in filtrados] == ["Mouse óptico"]


def test_paginacion(client):
    for i in range(4):
        _crear(client, nombre=f"Producto {i}")
    r = client.get("/productos", params={"skip": 1, "limit": 2})
    assert [p["nombre"] for p in r.json()] == ["Producto 1", "Producto 2"]


def test_precio_negativo_422(client):
    assert _crear(client, precio="-1").status_code == 422


def test_stock_negativo_422(client):
    assert _crear(client, stock=-3).status_code == 422


def test_precio_con_tres_decimales_422(client):
    assert _crear(client, precio="10.123").status_code == 422


def test_obtener_inexistente_404(client):
    assert client.get("/productos/999").status_code == 404


def test_actualizar_stock(client):
    pid = _crear(client).json()["id"]
    r = client.patch(f"/productos/{pid}", json={"stock": 2})
    assert r.status_code == 200
    assert r.json()["stock"] == 2
    assert r.json()["nombre"] == "Teclado"


def test_actualizar_inexistente_404(client):
    assert client.patch("/productos/999", json={"stock": 1}).status_code == 404


def test_eliminar(client):
    pid = _crear(client).json()["id"]
    assert client.delete(f"/productos/{pid}").status_code == 204
    assert client.get(f"/productos/{pid}").status_code == 404
