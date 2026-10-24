# Ruff + pytest (cobertura >= 80 %) + Bandit en los tres servicios; salidas en evidencias\
# Requiere: pip install -r requirements-dev.txt
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force evidencias | Out-Null
$fallos = 0

Write-Host "== Ruff (mantenibilidad)"
ruff check . 2>&1 | Tee-Object evidencias\ruff.txt
if ($LASTEXITCODE -ne 0) { $fallos++ }
ruff format --check . 2>&1 | Tee-Object -Append evidencias\ruff.txt
if ($LASTEXITCODE -ne 0) { $fallos++ }

foreach ($s in "usuarios", "productos", "pedidos") {
    Write-Host "== pytest $s (fiabilidad)"
    Push-Location $s
    pytest 2>&1 | Tee-Object "..\evidencias\pytest-$s.txt"
    if ($LASTEXITCODE -ne 0) { $fallos++ }
    Pop-Location
    Write-Host "== Bandit $s (seguridad)"
    bandit -r "$s\app" 2>&1 | Tee-Object "evidencias\bandit-$s.txt"
    if ($LASTEXITCODE -ne 0) { $fallos++ }
}

if ($fallos -eq 0) { Write-Host "CALIDAD: OK" -ForegroundColor Green }
else { Write-Host "CALIDAD: $fallos verificacion(es) fallida(s)" -ForegroundColor Red }
exit $fallos
