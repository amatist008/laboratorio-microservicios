
# Verificación funcional y de red
# Compatible con Windows PowerShell 5.1 y PowerShell 7+
# Uso:
# docker compose up --build -d --wait
# .\scripts\verificar.ps1

$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")

$Base = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost" }
$script:ok = 0
$script:ko = 0

function Pasa($m) {
    Write-Host "  [OK]    $m" -ForegroundColor Green
    $script:ok++
}

function Falla($m) {
    Write-Host "  [FALLA] $m" -ForegroundColor Red
    $script:ko++
}

function Invocar($Metodo, $Url, $Cuerpo) {
    try {
        $p = @{
            Uri             = $Url
            Method          = $Metodo
            UseBasicParsing = $true
            TimeoutSec      = 10
            ErrorAction     = "Stop"
        }

        if ($Cuerpo) {
            $p.Body = $Cuerpo
            $p.ContentType = "application/json"
        }

        $r = Invoke-WebRequest @p

        return @{
            Codigo  = [int]$r.StatusCode
            Headers = $r.Headers
        }
    }
    catch {
        if ($_.Exception.Response) {
            try {
                $codigo = [int]$_.Exception.Response.StatusCode
            }
            catch {
                $codigo = 0
            }

            return @{ Codigo = $codigo; Headers = @{} }
        }

        return @{ Codigo = 0; Headers = @{} }
    }
}

Write-Host "1. Enrutamiento a traves de Nginx -> Kong -> servicio"

foreach ($r in "usuarios", "productos", "pedidos") {
    $c = (Invocar GET "$Base/$r" $null).Codigo

    if ($c -eq 200) {
        Pasa "GET /$r -> 200"
    }
    else {
        Falla "GET /$r -> $c"
    }

    $c = (Invocar GET "$Base/$r/health" $null).Codigo

    if ($c -eq 200) {
        Pasa "GET /$r/health -> 200"
    }
    else {
        Falla "GET /$r/health -> $c"
    }
}

$c = (Invocar GET "$Base/ruta-inexistente" $null).Codigo

if ($c -eq 404) {
    Pasa "Ruta no registrada en Kong -> 404"
}
else {
    Falla "Ruta no registrada -> $c"
}

Write-Host "2. Balanceo de carga entre los nodos de Kong"

$nodos = @(
    1..10 | ForEach-Object {
        (Invocar GET "$Base/usuarios" $null).Headers["X-Gateway-Node"]
    } | Where-Object { $_ } | Sort-Object -Unique
)

if ($nodos.Count -ge 2) {
    Pasa "10 peticiones repartidas entre $($nodos.Count) nodos"
}
else {
    Falla "Solo un nodo atendio o no se detectaron los encabezados"
}

Write-Host "3. Comunicacion entre servicios"

$c = (Invocar POST "$Base/pedidos" '{"usuario_id":1,"producto_id":1,"cantidad":1}').Codigo

if ($c -eq 201) {
    Pasa "POST /pedidos valido -> 201"
}
else {
    Falla "POST /pedidos -> $c"
}

$c = (Invocar POST "$Base/pedidos" '{"usuario_id":9999,"producto_id":1,"cantidad":1}').Codigo

if ($c -eq 422) {
    Pasa "POST /pedidos usuario inexistente -> 422"
}
else {
    Falla "Usuario inexistente -> $c"
}

Write-Host "4. Seguridad de red"

$nginx = docker compose ps -q nginx 2>$null

if (-not $nginx) {
    Falla "La pila de Docker Compose no esta en ejecucion"
    Write-Host ""
    Write-Host "Resultado: $script:ok correctas, $script:ko fallidas"
    exit $script:ko
}

# Comprobar publicaciones reales de los puertos PostgreSQL.
# No usar 'docker compose port' para esta comprobacion:
# puede devolver 'invalid IP:0' en determinadas versiones.
foreach ($db in "db-usuarios", "db-productos", "db-pedidos") {
    $id = docker compose ps -q $db 2>$null

    if (-not $id) {
        Falla "${db}: no se encontro el contenedor"
        continue
    }

    $bindings = docker inspect --format '{{json .HostConfig.PortBindings}}' $id 2>$null

    if ($LASTEXITCODE -ne 0 -or -not $bindings) {
        Falla "${db}: no se pudo comprobar la configuracion"
        continue
    }

    try {
        $config = $bindings | ConvertFrom-Json
        $puerto = $config.'5432/tcp'

        if ($null -eq $puerto -or @($puerto).Count -eq 0) {
            Pasa "${db}:5432 no expuesto al anfitrion"
        }
        else {
            Falla "${db}:5432 tiene una publicacion configurada"
        }
    }
    catch {
        Falla "${db}: no se pudo interpretar la configuracion de puertos"
    }
}

# Comprobar si el puerto 5432 del equipo anfitrion acepta conexiones.
$t = Test-NetConnection `
    -ComputerName localhost `
    -Port 5432 `
    -WarningAction SilentlyContinue

if (-not $t.TcpTestSucceeded) {
    Pasa "localhost:5432 rechaza conexiones"
}
else {
    Write-Host "  [AVISO] Algo escucha en localhost:5432; revisar si corresponde a PostgreSQL." -ForegroundColor Yellow
}

# Verificar que pedidos no pueda resolver el nombre de la BD de usuarios.
docker compose exec -T pedidos python -c "import socket; socket.gethostbyname('db-usuarios')" 2>$null | Out-Null

if ($LASTEXITCODE -ne 0) {
    Pasa "pedidos NO alcanza la BD de usuarios"
}
else {
    Falla "pedidos resuelve db-usuarios"
}

# Verificar que usuarios no tenga salida a Internet.
docker compose exec -T usuarios python -c "import urllib.request; urllib.request.urlopen('https://pypi.org', timeout=4)" 2>$null | Out-Null

if ($LASTEXITCODE -ne 0) {
    Pasa "Red privada sin salida a Internet"
}
else {
    Falla "usuarios tiene salida a Internet"
}

Write-Host ""
Write-Host "Resultado: $script:ok correctas, $script:ko fallidas"

exit $script:ko

