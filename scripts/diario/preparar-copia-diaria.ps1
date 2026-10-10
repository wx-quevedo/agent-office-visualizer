<#
.SYNOPSIS
  Prepara la copia diaria la primera vez: clona, configura los datos, instala y compila.

.DESCRIPTION
  1. Clona el repositorio (rama main) en E:\visualizador-agentes-diario si no existe.
     Origen por defecto: la copia de desarrollo E:\visualizador-agentes (así trae
     los commits locales aunque no se hayan subido); se puede pasar -Origen con
     la URL de GitHub.
  2. Crea la carpeta de datos fuera de los repositorios y el backend\.env de la
     copia diaria (bases de datos, CORS para 3000 y Tailscale, sin resúmenes).
  3. Si se indica -CopiarHistoria, copia una vez el agent_events.db de desarrollo
     (con la copia de desarrollo DETENIDA) para no empezar sin historia.
  4. Instala dependencias y compila el frontend.
  No arranca la oficina: para eso está iniciar-oficina.ps1.
#>
param(
    [string]$Origen = 'E:\visualizador-agentes',
    [switch]$CopiarHistoria
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

Write-Host "Oficina de agentes (copia diaria) - preparar"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$log = Join-Path $Logs 'preparar.log'

if (Test-Path (Join-Path $Raiz '.git')) {
    Escribir-Paso "La copia ya existe en $Raiz (no se vuelve a clonar)"
} else {
    Invoke-Paso "Clonando $Origen (rama main) en $Raiz" "git clone --branch main `"$Origen`" `"$Raiz`"" (Split-Path $Raiz) $log
}

$datosSql = $Datos -replace '\\', '/'
$env_ = Join-Path $DirBackend '.env'
if (Test-Path $env_) {
    Escribir-Paso "Ya existe $env_ (no se sobrescribe)"
} else {
    @"
# Copia DIARIA de la oficina (E:\visualizador-agentes-diario, puertos 3000/8000).
# Generado por scripts/diario/preparar-copia-diaria.ps1. No versionado.
# Sus datos viven fuera de los repositorios para no mezclarse con desarrollo.
DATABASE_URL=sqlite+aiosqlite:///$datosSql/visualizer.db
STATE_EVENT_LOG_PATH=$datosSql/agent_events.db
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://${IpTailscale}:3000","http://localhost:8000","http://127.0.0.1:8000"]
SUMMARY_BACKEND=disabled
EVENT_RATE_LIMIT=100000
"@ | Set-Content -Path $env_ -Encoding UTF8
    Escribir-Paso "Creado $env_ (datos en $Datos)"
}

if ($CopiarHistoria) {
    $desarrollo = 'E:\visualizador-agentes\backend\agent_events.db'
    $destino = Join-Path $Datos 'agent_events.db'
    if (Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue) {
        throw "La copia de desarrollo está corriendo (8100): detenla antes de copiar su historia."
    }
    if (Test-Path $destino) {
        Escribir-Paso "Ya hay historia en $destino (no se copia encima)"
    } elseif (Test-Path $desarrollo) {
        foreach ($sufijo in @('', '-wal', '-shm')) {
            if (Test-Path "$desarrollo$sufijo") { Copy-Item "$desarrollo$sufijo" "$destino$sufijo" }
        }
        Escribir-Paso "Historia copiada una vez desde $desarrollo"
    }
}

Invoke-Paso "Dependencias del backend (uv sync)" "uv sync --frozen" $DirBackend $log
Invoke-Paso "Dependencias del frontend (npm install)" "npm install --no-audit --no-fund" $DirFrontend $log
$env:NEXT_PUBLIC_BACKEND_PORT = "$PuertoBackend"
Invoke-Paso "Compilando el frontend (next build)" "npm run build" $DirFrontend $log
Write-Host "Copia diaria preparada. Para arrancarla: scripts\diario\iniciar-oficina.ps1"
