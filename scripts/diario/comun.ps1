# Configuración y funciones comunes de los scripts de la copia diaria.
# Se carga con:  . "$PSScriptRoot\comun.ps1"
#
# Copia diaria: E:\visualizador-agentes-diario (puertos 3000 y 8000).
# Copia de desarrollo: E:\visualizador-agentes (3100 y 8100). Estos scripts
# nunca tocan procesos de la copia de desarrollo, VS Code ni Claude Code.

# Acentos: git, uv y npm escriben UTF-8, pero Windows PowerShell 5.1 lee la
# salida de los programas con la página de códigos de la consola (850) y
# "está" salía como "est├í". Se lee y se escribe en UTF-8. Sin consola (tarea
# programada oculta) no hay nada que ajustar.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }
$OutputEncoding = New-Object System.Text.UTF8Encoding $false

$Raiz = if ($env:VISUALIZADOR_DIARIO_RAIZ) { $env:VISUALIZADOR_DIARIO_RAIZ } else { 'E:\visualizador-agentes-diario' }
$Datos = if ($env:VISUALIZADOR_DIARIO_DATOS) { $env:VISUALIZADOR_DIARIO_DATOS } else { Join-Path $env:USERPROFILE '.visualizador-agentes\datos-diario' }
$Logs = Join-Path $Datos 'logs'
$PuertoBackend = 8000
$PuertoFrontend = 3000
$IpTailscale = '<TAILSCALE_IP>'
$DirBackend = Join-Path $Raiz 'backend'
$DirFrontend = Join-Path $Raiz 'frontend'
$DirExport = Join-Path $DirFrontend 'out'
$Uvicorn = Join-Path $DirBackend '.venv\Scripts\uvicorn.exe'
$Python = Join-Path $DirBackend '.venv\Scripts\python.exe'
$NombreTarea = 'Oficina de agentes (diaria)'

function Escribir-Paso([string]$texto) {
    Write-Host "  - $texto"
}

function Test-ComandoDiario([string]$linea) {
    # Pertenece a la copia diaria: su línea de comandos contiene la ruta de la copia.
    if (-not $linea) { return $false }
    return $linea.ToLower().Contains($Raiz.ToLower().TrimEnd('\'))
}

function Get-ProcesosDiario {
    # Solo los servidores de la copia diaria: python/uvicorn y el cmd que los lanza.
    Get-CimInstance Win32_Process | Where-Object {
        (Test-ComandoDiario $_.CommandLine) -and (
            $_.Name -match '^(python|pythonw|uvicorn)\.exe$' -or
            ($_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'uvicorn|servidor_frontend')
        )
    }
}

function Get-DuenoPuerto([int]$puerto) {
    $conexion = Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conexion) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId=$($conexion.OwningProcess)"
}

function Test-Url([string]$url) {
    try {
        return (Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 4).StatusCode
    } catch {
        return $null
    }
}

function Esperar-Url([string]$url, [int]$segundos) {
    $limite = (Get-Date).AddSeconds($segundos)
    while ((Get-Date) -lt $limite) {
        if ((Test-Url $url) -eq 200) { return $true }
        Start-Sleep -Milliseconds 700
    }
    return $false
}

function Rotar-Log([string]$archivo) {
    # Un respaldo (.1) cuando el registro pasa de 5 MB.
    if ((Test-Path $archivo) -and ((Get-Item $archivo).Length -gt 5MB)) {
        Move-Item -Force $archivo "$archivo.1"
    }
}

function Iniciar-Oculto([string]$comando, [string]$directorio, [string]$log) {
    # Proceso desacoplado de esta consola y sin ventana: sigue vivo al cerrar
    # la terminal o al terminar la tarea programada. Salida al archivo de registro.
    Rotar-Log $log
    $linea = "cmd.exe /d /c `"$comando >> `"$log`" 2>&1`""
    $inicio = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $linea
        CurrentDirectory = $directorio
        ProcessStartupInformation = $inicio
    }
    if ($r.ReturnValue -ne 0) { throw "No se pudo iniciar: $comando (código $($r.ReturnValue))" }
    return $r.ProcessId
}

function Detener-ProcesosDiario {
    # Termina el árbol de cada proceso de la copia diaria. Nada más.
    $procesos = @(Get-ProcesosDiario)
    foreach ($p in $procesos) {
        if (Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue) {
            # Via cmd: a process already gone with its tree is not an error here.
            & cmd.exe /d /c "taskkill /PID $($p.ProcessId) /T /F >nul 2>&1"
        }
    }
    return $procesos.Count
}

function Invoke-Paso([string]$descripcion, [string]$comando, [string]$directorio, [string]$log) {
    # Comando nativo con su salida al registro; error si devuelve código distinto de 0.
    Escribir-Paso $descripcion
    Add-Content -Path $log -Value "`r`n== $(Get-Date -Format s) $descripcion :: $comando" -Encoding UTF8
    Push-Location $directorio
    try {
        & cmd.exe /d /c "$comando >> `"$log`" 2>&1"
        $codigo = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($codigo -ne 0) { throw "Falló: $descripcion (código $codigo). Detalle en $log" }
}
