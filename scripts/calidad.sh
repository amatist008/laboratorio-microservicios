#!/usr/bin/env bash
# Ejecuta Ruff, pytest (cobertura >= 80 %) y Bandit en los tres servicios
# y guarda las salidas en evidencias/. Requiere: pip install -r requirements-dev.txt
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p evidencias
fallos=0

echo "== Ruff (mantenibilidad)"
{ ruff check . && ruff format --check . ; } 2>&1 | tee evidencias/ruff.txt || fallos=$((fallos + 1))

for s in usuarios productos pedidos; do
  echo "== pytest $s (fiabilidad)"
  (cd "$s" && pytest) 2>&1 | tee "evidencias/pytest-$s.txt" || fallos=$((fallos + 1))
  echo "== Bandit $s (seguridad)"
  bandit -r "$s/app" 2>&1 | tee "evidencias/bandit-$s.txt" || fallos=$((fallos + 1))
done

echo
if [ "$fallos" -eq 0 ]; then echo "CALIDAD: OK"; else echo "CALIDAD: $fallos verificación(es) fallida(s)"; fi
exit "$fallos"
