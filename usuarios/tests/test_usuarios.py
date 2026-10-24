from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


def _crear(client, nombre="Ana Gómez", email="ana@example.com"):
    return client.post("/usuarios", json={"nombre": nombre, "email": email})


def test_health_ok(client):
    r = client.get("/usuarios/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "servicio": "usuarios"}


def test_health_bd_caida_responde_503(client):
    class SesionRota:
        def execute(self, *_):
            raise OperationalError("SELECT 1", {}, Exception("sin conexión"))

    app.dependency_overrides[get_db] = lambda: SesionRota()
    r = client.get("/usuarios/health")
    assert r.status_code == 503


def test_listar_vacio(client):
    r = client.get("/usuarios")
    assert r.status_code == 200
    assert r.json() == []


def test_crear_y_obtener(client):
    r = _crear(client)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["id"] > 0
    assert cuerpo["email"] == "ana@example.com"

    r = client.get(f"/usuarios/{cuerpo['id']}")
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ana Gómez"


def test_email_duplicado_409(client):
    _crear(client)
    r = _crear(client, nombre="Otra Ana")
    assert r.status_code == 409


def test_validacion_email_invalido_422(client):
    r = _crear(client, email="no-es-un-email")
    assert r.status_code == 422


def test_paginacion(client):
    for i in range(5):
        _crear(client, nombre=f"Usuario {i}", email=f"u{i}@example.com")
    r = client.get("/usuarios", params={"skip": 2, "limit": 2})
    assert r.status_code == 200
    assert [u["nombre"] for u in r.json()] == ["Usuario 2", "Usuario 3"]


def test_limite_fuera_de_rango_422(client):
    assert client.get("/usuarios", params={"limit": 1000}).status_code == 422


def test_obtener_inexistente_404(client):
    assert client.get("/usuarios/999").status_code == 404


def test_actualizar_parcial(client):
    uid = _crear(client).json()["id"]
    r = client.patch(f"/usuarios/{uid}", json={"nombre": "Ana María"})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ana María"
    assert r.json()["email"] == "ana@example.com"


def test_actualizar_email_duplicado_409(client):
    _crear(client)
    uid = _crear(client, nombre="Luis", email="luis@example.com").json()["id"]
    r = client.patch(f"/usuarios/{uid}", json={"email": "ana@example.com"})
    assert r.status_code == 409


def test_eliminar(client):
    uid = _crear(client).json()["id"]
    assert client.delete(f"/usuarios/{uid}").status_code == 204
    assert client.get(f"/usuarios/{uid}").status_code == 404


def test_eliminar_inexistente_404(client):
    assert client.delete("/usuarios/999").status_code == 404


def test_documentacion_expuesta_bajo_prefijo(client):
    assert client.get("/usuarios/openapi.json").status_code == 200
