"""Prueba de carga (desempeño) a través del punto de entrada público.

Uso (sin interfaz):
    locust -f locust/locustfile.py --headless -u 100 -r 10 -t 30s -H http://localhost \
        --csv evidencias/locust --html evidencias/locust.html

Criterio de aceptación: p95 <= 2000 ms y 0 % de fallos.
El proceso termina con código 1 si no se cumple (útil en CI).
"""

import random
import uuid

from locust import HttpUser, between, events, task

UMBRAL_P95_MS = 2000


class ClienteTienda(HttpUser):
    wait_time = between(0.5, 2)

    @task(4)
    def listar_productos(self):
        self.client.get("/productos", name="GET /productos")

    @task(3)
    def listar_usuarios(self):
        self.client.get("/usuarios", name="GET /usuarios")

    @task(3)
    def listar_pedidos(self):
        self.client.get("/pedidos", name="GET /pedidos")

    @task(2)
    def ver_producto(self):
        self.client.get(f"/productos/{random.randint(1, 3)}", name="GET /productos/{id}")

    @task(1)
    def registrar_usuario(self):
        sufijo = uuid.uuid4().hex[:10]
        self.client.post(
            "/usuarios",
            json={"nombre": f"Carga {sufijo}", "email": f"carga-{sufijo}@example.com"},
            name="POST /usuarios",
        )

    @task(1)
    def crear_pedido(self):
        # Llamada que atraviesa dos servicios (pedidos -> usuarios y productos)
        self.client.post(
            "/pedidos",
            json={"usuario_id": 1, "producto_id": random.randint(1, 3), "cantidad": 1},
            name="POST /pedidos",
        )


@events.quitting.add_listener
def verificar_criterios(environment, **_kwargs):
    total = environment.stats.total
    p95 = total.get_response_time_percentile(0.95)
    if total.num_failures > 0:
        print(f"[FALLA] {total.num_failures} peticiones fallidas")
        environment.process_exit_code = 1
    elif p95 > UMBRAL_P95_MS:
        print(f"[FALLA] p95 = {p95:.0f} ms supera {UMBRAL_P95_MS} ms")
        environment.process_exit_code = 1
    else:
        print(f"[OK] p95 = {p95:.0f} ms, 0 fallos, {total.num_requests} peticiones")
        environment.process_exit_code = 0
