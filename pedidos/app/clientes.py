"""Clientes HTTP hacia los otros microservicios (comunicación este-oeste).

Pedidos NUNCA lee las bases de datos de usuarios o productos: consulta sus APIs.
Se usa un único httpx.Client por proceso para reutilizar conexiones (keep-alive),
lo que evita pagar el establecimiento TCP en cada pedido.
"""

import os
from functools import lru_cache
from typing import Any

import httpx


class ServicioNoDisponibleError(Exception):
    """El servicio remoto no respondió o respondió con error 5xx."""


class ClienteServicios:
    def __init__(
        self,
        usuarios_url: str,
        productos_url: str,
        timeout: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.usuarios_url = usuarios_url.rstrip("/")
        self.productos_url = productos_url.rstrip("/")
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    def _obtener(self, url: str) -> dict[str, Any] | None:
        try:
            respuesta = self._http.get(url)
        except httpx.HTTPError as exc:
            raise ServicioNoDisponibleError(str(exc)) from exc
        if respuesta.status_code == 404:
            return None
        if respuesta.status_code >= 400:
            raise ServicioNoDisponibleError(f"{url} respondió {respuesta.status_code}")
        return respuesta.json()

    def obtener_usuario(self, usuario_id: int) -> dict[str, Any] | None:
        return self._obtener(f"{self.usuarios_url}/usuarios/{usuario_id}")

    def obtener_producto(self, producto_id: int) -> dict[str, Any] | None:
        return self._obtener(f"{self.productos_url}/productos/{producto_id}")


@lru_cache(maxsize=1)
def get_clientes() -> ClienteServicios:
    """Dependencia de FastAPI: una instancia compartida por proceso (reemplazable en pruebas)."""
    return ClienteServicios(
        usuarios_url=os.getenv("USUARIOS_URL", "http://usuarios:8000"),
        productos_url=os.getenv("PRODUCTOS_URL", "http://productos:8000"),
    )
