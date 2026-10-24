# Laboratorio · Arquitectura de microservicios con Python y FastAPI

Tres microservicios FastAPI (usuarios, productos, pedidos), cada uno con su propia base PostgreSQL,
detrás de un API Gateway (Kong OSS, modo DB-less) y un balanceador (Nginx). Todo se ejecuta en un
solo equipo con **un comando**, usando únicamente herramientas gratuitas y de código abierto.

```
Cliente ──► Nginx :80 ──► Kong 1 / Kong 2 ──► usuarios ──► PostgreSQL (usuarios)
            (único        (enrutamiento        productos ──► PostgreSQL (productos)
             puerto)       por prefijo)        pedidos   ──► PostgreSQL (pedidos)
```

Diagrama completo, matriz de alcanzabilidad y decisiones de diseño: [`docs/arquitectura.md`](docs/arquitectura.md).

---

## 1. Requisitos previos

| Herramienta | Versión mínima | Nota |
|---|---|---|
| Docker Engine + Compose v2 | 24 / 2.20 | En Windows y macOS: Docker Desktop (gratuito para uso educativo) |
| Python | 3.12 | Solo para ejecutar pruebas y Locust en el anfitrión |
| Git, VS Code | — | |

El puerto **80** del equipo debe estar libre. Si no lo está, cree un `.env` con `HTTP_PORT=8080`
y use `http://localhost:8080` en todos los comandos.

## 2. Despliegue (un solo comando)

```bash
docker compose up --build -d --wait
```

`--wait` bloquea hasta que **todos** los contenedores reportan `healthy`. El orden de arranque lo
garantizan los `healthcheck` y `depends_on`:

```
PostgreSQL (pg_isready) ─► servicios (alembic upgrade head + /health) ─► Kong (kong health) ─► Nginx
```

Al iniciar, cada servicio aplica sus migraciones Alembic y carga datos semilla (3 usuarios,
3 productos, 2 pedidos). Para apagar: `docker compose down` (añada `-v` para borrar los datos).

Documentación interactiva (Swagger), a través del gateway:
- http://localhost/usuarios/docs
- http://localhost/productos/docs
- http://localhost/pedidos/docs

## 3. Verificación

```bash
bash scripts/verificar.sh          # Linux / macOS / Git Bash
.\scripts\verificar.ps1            # Windows PowerShell
```

El script comprueba enrutamiento, balanceo entre los dos nodos de Kong, comunicación entre servicios,
que ninguna base de datos esté expuesta, que `pedidos` no pueda alcanzar la BD de `usuarios` y que la
red privada no tenga salida a Internet. Equivalente manual de la guía:

```bash
curl http://localhost/usuarios                  # 200 + JSON
curl http://localhost/productos                 # 200
curl http://localhost/pedidos                   # 200
psql -h localhost -p 5432 -U postgres           # conexión rechazada
curl -sI http://localhost/usuarios | grep -i x-gateway-node   # repita: alterna entre nodos
```

## 4. Calidad

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
bash scripts/calidad.sh                                # Windows: .\scripts\calidad.ps1
```

Prueba de carga (con la arquitectura levantada):

```bash
locust -f locust/locustfile.py --headless -u 100 -r 10 -t 30s -H http://localhost \
       --only-summary --csv evidencias/locust --html evidencias/locust.html
```

El `locustfile` termina con código 1 si el p95 supera 2 s o si hay fallos, de modo que sirve como
criterio de aceptación automático (también en CI).

## 5. Requisitos de calidad especificados con métricas

Clasificados según las características de ISO/IEC 25010.

| ID | Característica (ISO/IEC 25010) | Requisito | Métrica | Umbral | Herramienta |
|---|---|---|---|---|---|
| RC-01 | Mantenibilidad · analizabilidad | El código cumple el estilo y no tiene errores estáticos | Advertencias de Ruff (E, W, F, I, B, UP, S, SIM, N) | 0 | `ruff check . && ruff format --check .` |
| RC-02 | Fiabilidad · madurez | Cada endpoint tiene pruebas automáticas, incluidos casos de error | Cobertura de líneas por servicio | ≥ 80 % | `pytest --cov=app --cov-fail-under=80` |
| RC-03 | Seguridad · integridad | Sin vulnerabilidades en el código fuente | Hallazgos Bandit de severidad media o alta | 0 | `bandit -r app` |
| RC-04 | Eficiencia de desempeño · comportamiento temporal | Respuesta oportuna bajo carga concurrente | Percentil 95 del tiempo de respuesta con 100 usuarios, 30 s | ≤ 2 000 ms | Locust |
| RC-05 | Fiabilidad · tolerancia a fallos | Sin errores bajo carga | Tasa de fallos HTTP | 0 % | Locust |
| RC-06 | Seguridad · confidencialidad | Las bases de datos no son accesibles desde fuera | Puertos de BD publicados en el anfitrión | 0 | `scripts/verificar.sh` |
| RC-07 | Seguridad · confidencialidad | Aislamiento de datos entre servicios | Servicios capaces de resolver la BD de otro | 0 | `scripts/verificar.sh` |
| RC-08 | Disponibilidad | El sistema arranca completo y sano con un comando | Contenedores `healthy` tras `up --wait` | 9/9 | Docker Compose |
| RC-09 | Fiabilidad · disponibilidad | La sonda `/health` refleja el estado real de la BD | Código ante BD caída | 503 | pytest |

### Resultados de línea base

Medidos durante el desarrollo **sin contenedores** (PostgreSQL 16 nativo, los tres servicios con
Uvicorn de 2 workers, el `nginx.conf` del proyecto como balanceador y dos nodos de gateway). Las
salidas están en `evidencias/linea-base-sin-docker/`. **Deben repetirse con Docker** para la entrega.

| ID | Resultado |
|---|---|
| RC-01 | 0 advertencias, 31 archivos formateados |
| RC-02 | usuarios 95,8 % (14 pruebas) · productos 96,1 % (12) · pedidos 97,3 % (19) |
| RC-03 | 0 hallazgos (bajo, medio y alto) en los tres servicios |
| RC-04 | p95 = 27 ms (2 085 peticiones, ~69 req/s) |
| RC-05 | 0 fallos |

Hallazgo de desempeño documentado: en la primera medición, `POST /pedidos` tenía una mediana de
160 ms porque abría una conexión TCP nueva hacia `usuarios` y `productos` en cada petición. Al
reutilizar un `httpx.Client` con *pool* de conexiones por proceso, bajó a 20 ms (p95 global: de
130 ms a 27 ms).

## 6. API

| Método | Ruta | Descripción | Códigos |
|---|---|---|---|
| GET | `/{servicio}/health` | Estado del servicio y su BD | 200, 503 |
| GET | `/usuarios?skip&limit` | Listar (paginado, `limit` ≤ 100) | 200, 422 |
| GET | `/usuarios/{id}` | Obtener | 200, 404 |
| POST | `/usuarios` | Crear (`nombre`, `email`) | 201, 409 email duplicado, 422 |
| PATCH | `/usuarios/{id}` | Actualización parcial | 200, 404, 409 |
| DELETE | `/usuarios/{id}` | Eliminar | 204, 404 |
| GET | `/productos?q&skip&limit` | Listar, filtro por nombre | 200 |
| POST/PATCH/DELETE | `/productos[/{id}]` | CRUD (`precio` ≥ 0 con 2 decimales, `stock` ≥ 0) | 201/200/204, 404, 422 |
| GET | `/pedidos?usuario_id` | Listar, filtro por usuario | 200 |
| POST | `/pedidos` | Crear: valida usuario y producto **vía API**, verifica stock y calcula total | 201, 409 sin stock, 422 inexistente, 503 dependencia caída |
| PATCH | `/pedidos/{id}/estado` | `pendiente → pagado → enviado`, o `cancelado` | 200, 409 transición inválida |

## 7. Estructura

```
laboratorio/
├─ docker-compose.yml        # toda la arquitectura
├─ nginx/nginx.conf          # balanceador (least_conn entre 2 nodos de Kong)
├─ kong/kong.yml             # rutas y plugins del gateway (DB-less)
├─ usuarios/ productos/ pedidos/
│  ├─ app/                   # main.py, models.py, schemas.py, database.py (+ clientes.py en pedidos)
│  ├─ migrations/            # Alembic: esquema + datos semilla
│  ├─ tests/                 # pytest con SQLite en memoria
│  ├─ Dockerfile             # python:3.12-slim, usuario sin privilegios, healthcheck
│  └─ requirements.txt
├─ locust/locustfile.py      # carga con criterio de aceptación automático
├─ scripts/                  # verificar.(sh|ps1), calidad.(sh|ps1)
├─ docs/arquitectura.md      # diagrama y decisiones
├─ evidencias/               # salidas de pruebas (entregable 4)
├─ .github/workflows/ci.yml  # calidad por servicio + integración con Docker + carga
├─ ruff.toml · requirements-dev.txt · .env.example
```

## 8. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `Bind for 0.0.0.0:80 failed: port is already allocated` | IIS, Apache o Skype ocupan el 80. Ponga `HTTP_PORT=8080` en `.env`. |
| `dependency failed to start: container ... is unhealthy` | `docker compose logs <servicio>`. Casi siempre es una migración o una contraseña con caracteres `@ : / #` que rompe la URL. |
| Cambió la contraseña en `.env` y ahora el servicio no conecta | PostgreSQL solo usa `POSTGRES_PASSWORD` al crear el volumen. `docker compose down -v` y vuelva a levantar. |
| Kong responde `no Route matched` | La ruta no empieza por `/usuarios`, `/productos` o `/pedidos`. |
| Kong responde `429` | Se superó el límite de 300 peticiones/s por IP del plugin `rate-limiting`. |
| Los scripts `.sh` fallan con `$'\r': command not found` | Finales de línea CRLF. El `.gitattributes` lo evita al clonar; si copió los archivos a mano, conviértalos a LF. |

## 9. Nota sobre versiones

Se usa la imagen oficial `kong:3.9` (edición OSS, 3.9.1 al momento de escribir esto). Si en el futuro
ese tag cambia, basta con ajustar `image:` en el bloque `x-kong` del `docker-compose.yml`. Las versiones de las
dependencias de Python están fijadas en `requirements.txt` para que la construcción sea reproducible.
