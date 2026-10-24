#!/usr/bin/env bash
# Verificación funcional y de red de la arquitectura desplegada con Docker Compose.
# Uso:  docker compose up --build -d --wait   y luego   bash scripts/verificar.sh
set -uo pipefail
cd "$(dirname "$0")/.."
BASE="${BASE_URL:-http://localhost}"
ok=0; ko=0
pasa()  { echo "  [OK]    $1"; ok=$((ok + 1)); }
falla() { echo "  [FALLA] $1"; ko=$((ko + 1)); }
codigo() { curl -s -o /dev/null -w "%{http_code}" "$@"; }

echo "1. Enrutamiento a través de Nginx -> Kong -> servicio"
for r in usuarios productos pedidos; do
  c=$(codigo "$BASE/$r")
  [ "$c" = "200" ] && pasa "GET /$r -> 200" || falla "GET /$r -> $c"
  c=$(codigo "$BASE/$r/health")
  [ "$c" = "200" ] && pasa "GET /$r/health -> 200 (BD alcanzable)" || falla "GET /$r/health -> $c"
done
c=$(codigo "$BASE/ruta-inexistente")
[ "$c" = "404" ] && pasa "Ruta no registrada en Kong -> 404" || falla "Ruta no registrada -> $c"

echo "2. Balanceo de carga entre los nodos de Kong"
nodos=$(for _ in $(seq 1 10); do curl -s -D - -o /dev/null "$BASE/usuarios" | grep -i '^x-gateway-node' | tr -d '\r'; done | sort -u | wc -l)
[ "$nodos" -ge 2 ] && pasa "10 peticiones repartidas entre $nodos nodos" || falla "solo $nodos nodo(s) atendió(eron)"

echo "3. Comunicación entre servicios (pedidos consulta usuarios y productos)"
c=$(codigo -X POST "$BASE/pedidos" -H 'Content-Type: application/json' \
      -d '{"usuario_id":1,"producto_id":1,"cantidad":1}')
[ "$c" = "201" ] && pasa "POST /pedidos válido -> 201" || falla "POST /pedidos -> $c"
c=$(codigo -X POST "$BASE/pedidos" -H 'Content-Type: application/json' \
      -d '{"usuario_id":9999,"producto_id":1,"cantidad":1}')
[ "$c" = "422" ] && pasa "POST /pedidos con usuario inexistente -> 422" || falla "usuario inexistente -> $c"

echo "4. Seguridad de red"
if [ -z "$(docker compose ps -q nginx 2>/dev/null)" ]; then
  falla "La pila de Docker Compose no está en ejecución: no se puede verificar la red"
  echo; echo "Resultado: $ok verificaciones correctas, $ko fallidas"; exit "$ko"
fi
publicados=$(docker compose ps --format '{{.Service}} {{.Publishers}}' | grep -v '^nginx' | grep -c 'PublishedPort:[1-9]' || true)
[ "$publicados" -eq 0 ] && pasa "Solo Nginx publica puertos en el anfitrión" || falla "$publicados servicio(s) adicional(es) publican puertos"
for db in db-usuarios db-productos db-pedidos; do
  [ -z "$(docker compose port "$db" 5432 2>/dev/null)" ] && pasa "$db:5432 no expuesto al anfitrión" || falla "$db:5432 expuesto"
done
if docker compose exec -T pedidos python -c "import socket; socket.gethostbyname('db-usuarios')" >/dev/null 2>&1; then
  falla "pedidos puede resolver db-usuarios (aislamiento de datos roto)"
else
  pasa "pedidos NO alcanza la BD de usuarios (una BD por servicio)"
fi
if docker compose exec -T usuarios python -c "import urllib.request; urllib.request.urlopen('https://pypi.org', timeout=4)" >/dev/null 2>&1; then
  falla "usuarios tiene salida a Internet"
else
  pasa "Red privada sin salida a Internet (internal: true)"
fi
if command -v psql >/dev/null 2>&1; then
  if PGCONNECT_TIMEOUT=3 psql -h localhost -p 5432 -U postgres -c 'select 1' >/dev/null 2>&1; then
    echo "  [AVISO] Algo responde en localhost:5432. Si tiene PostgreSQL instalado en el equipo es ese, no el del laboratorio."
  else
    pasa "psql -h localhost -p 5432 rechazado"
  fi
fi

echo
echo "Resultado: $ok verificaciones correctas, $ko fallidas"
exit "$ko"
