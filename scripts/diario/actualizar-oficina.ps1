<#
.SYNOPSIS
  Actualiza la copia diaria: detiene, git pull, instala dependencias, compila y arranca.

.DESCRIPTION
  Si algo falla (pull, dependencias o compilación), vuelve al commit anterior,
  restaura el frontend compilado anterior, arranca esa versión y lo informa.
  Nunca edita código: solo trae commits del origen de la copia diaria.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

Write-Host "Oficina de agentes (copia diaria) - actualizar"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$log = Join-Path $Logs 'actualizar.log'
Rotar-Log $log
$respaldoOut = Join-Path $Datos 'frontend-out-anterior'
$iniciar = Join-Path $Raiz 'scripts\diario\iniciar-oficina.ps1'
if (-not (Test-Path $iniciar)) { $iniciar = Join-Path $PSScriptRoot 'iniciar-oficina.ps1' }

$anterior = (& git -C $Raiz rev-parse HEAD).Trim()
Escribir-Paso "Versión actual: $(& git -C $Raiz log -1 --format='%h %s')"

# Respaldo del frontend compilado para volver atrás sin recompilar.
if (Test-Path (Join-Path $DirExport 'index.html')) {
    if (Test-Path $respaldoOut) { Remove-Item -Recurse -Force $respaldoOut }
    Copy-Item -Recurse $DirExport $respaldoOut
}

Escribir-Paso "Deteniendo la copia diaria"
Detener-ProcesosDiario | Out-Null
Start-Sleep -Seconds 1

try {
    Invoke-Paso "Trayendo cambios (git pull)" "git -C `"$Raiz`" pull --ff-only" $Raiz $log
    $nuevo = (& git -C $Raiz rev-parse HEAD).Trim()
    Invoke-Paso "Dependencias del backend (uv sync)" "uv sync --frozen" $DirBackend $log
    Invoke-Paso "Dependencias del frontend (npm install)" "npm install --no-audit --no-fund" $DirFrontend $log
    # El frontend busca el backend en el puerto 8000 del mismo host.
    $env:NEXT_PUBLIC_BACKEND_PORT = "$PuertoBackend"
    Invoke-Paso "Compilando el frontend (next build)" "npm run build" $DirFrontend $log
    if (-not (Test-Path (Join-Path $DirExport 'index.html'))) { throw "La compilación no dejó $DirExport\index.html" }
} catch {
    Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Volviendo a la versión anterior ($($anterior.Substring(0, 7)))..." -ForegroundColor Yellow
    & git -C $Raiz reset --hard $anterior *>> $log
    if (Test-Path $respaldoOut) {
        if (Test-Path $DirExport) { Remove-Item -Recurse -Force $DirExport }
        Copy-Item -Recurse $respaldoOut $DirExport
    }
    Push-Location $DirBackend
    try { & cmd.exe /d /c "uv sync --frozen >> `"$log`" 2>&1" } finally { Pop-Location }
    & $iniciar
    Write-Host "La actualización falló; sigue funcionando la versión anterior. Detalle en $log" -ForegroundColor Red
    exit 1
}

if ($nuevo -eq $anterior) { Escribir-Paso "No había cambios nuevos" } else { Escribir-Paso "Actualizada a $(& git -C $Raiz log -1 --format='%h %s')" }
& $iniciar
