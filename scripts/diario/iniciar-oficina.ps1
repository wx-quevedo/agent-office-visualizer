<#
.SYNOPSIS
  Arranca la copia diaria de la oficina (backend 8000 y frontend 3000) en segundo plano.

.DESCRIPTION
  Sin ventanas y con registros en la carpeta de datos. Si ya está corriendo no
  duplica procesos; si un puerto lo usa otro programa (por ejemplo claude-office),
  no lo toca y avisa. Al final imprime las URLs.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

Write-Host "Oficina de agentes (copia diaria) - iniciar"
if (-not (Test-Path $Uvicorn)) { throw "Falta el entorno del backend en $DirBackend (.venv). Corre preparar-copia-diaria.ps1 o actualizar-oficina.ps1." }
if (-not (Test-Path (Join-Path $DirExport 'index.html'))) { throw "Falta el frontend compilado en $DirExport. Corre actualizar-oficina.ps1." }
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

function Mostrar-Resultado([bool]$okBackend, [bool]$okFrontend) {
    if (-not ($okBackend -and $okFrontend)) {
        Write-Host "No respondió a tiempo (backend: $okBackend, frontend: $okFrontend). Revisa los registros en $Logs" -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
    Write-Host "Lista. Abre:"
    Write-Host "  PC:      http://localhost:$PuertoFrontend/oficina    (3D: http://localhost:$PuertoFrontend/oficina/3d)"
    if ($IpTailscale) {
        Write-Host "  iPhone:  http://${IpTailscale}:$PuertoFrontend/oficina    (3D: http://${IpTailscale}:$PuertoFrontend/oficina/3d)"
    }
    Write-Host "  Datos:   $Datos"
}

# Con la tarea programada instalada, el arranque va siempre por ella: los
# servidores quedan fuera de la sesión que corre este script (una terminal,
# VS Code o Claude Code). Dentro de la tarea su estado es "Running" y el
# script arranca los procesos él mismo.
$tarea = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
if ($tarea -and $tarea.State -ne 'Running') {
    Start-ScheduledTask -TaskName $NombreTarea
    Escribir-Paso "Arranque a través de la tarea programada '$NombreTarea'"
    $okBackend = Esperar-Url "http://127.0.0.1:$PuertoBackend/health" 120
    $okFrontend = Esperar-Url "http://127.0.0.1:$PuertoFrontend/oficina" 30
    Mostrar-Resultado $okBackend $okFrontend
    exit 0
}

function Revisar-Puerto([int]$puerto) {
    # $true: ya lo atiende la copia diaria; $false: libre. Error si es de otro programa.
    $dueno = Get-DuenoPuerto $puerto
    if (-not $dueno) { return $false }
    if (Test-ComandoDiario $dueno.CommandLine) { return $true }
    throw "El puerto $puerto lo usa otro programa (PID $($dueno.ProcessId), $($dueno.Name)). No se inicia la oficina diaria para no pisarlo."
}

if (Revisar-Puerto $PuertoBackend) {
    Escribir-Paso "Backend ya corriendo en el puerto $PuertoBackend"
} else {
    $id = Iniciar-Oculto "`"$Uvicorn`" app.main:app --host 0.0.0.0 --port $PuertoBackend --loop asyncio:SelectorEventLoop" $DirBackend (Join-Path $Logs 'backend.log')
    Escribir-Paso "Backend iniciado (PID $id)"
}
if (Revisar-Puerto $PuertoFrontend) {
    Escribir-Paso "Frontend ya corriendo en el puerto $PuertoFrontend"
} else {
    $id = Iniciar-Oculto "`"$Python`" -m app.servidor_frontend --dir `"$DirExport`" --port $PuertoFrontend" $DirBackend (Join-Path $Logs 'frontend.log')
    Escribir-Paso "Frontend iniciado (PID $id)"
}

$okBackend = Esperar-Url "http://127.0.0.1:$PuertoBackend/health" 90
$okFrontend = Esperar-Url "http://127.0.0.1:$PuertoFrontend/oficina" 30
Mostrar-Resultado $okBackend $okFrontend
