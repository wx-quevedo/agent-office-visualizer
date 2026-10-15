<#
.SYNOPSIS
  Detiene solo la copia diaria de la oficina (puertos 3000 y 8000).

.DESCRIPTION
  Termina únicamente los procesos cuya línea de comandos contiene la ruta de la
  copia diaria (VISUALIZADOR_DIARIO_RAIZ). Nunca toca la copia de
  desarrollo, VS Code ni Claude Code.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

Write-Host "Oficina de agentes (copia diaria) - detener"
$n = Detener-ProcesosDiario
Start-Sleep -Seconds 1
Escribir-Paso "Procesos de la copia diaria detenidos: $n"
foreach ($puerto in @($PuertoBackend, $PuertoFrontend)) {
    $dueno = Get-DuenoPuerto $puerto
    if (-not $dueno) {
        Escribir-Paso "Puerto $puerto libre"
    } elseif (Test-ComandoDiario $dueno.CommandLine) {
        Write-Host "  - El puerto $puerto sigue ocupado por la copia diaria (PID $($dueno.ProcessId))" -ForegroundColor Yellow
    } else {
        Escribir-Paso "Puerto $puerto ocupado por otro programa (PID $($dueno.ProcessId), $($dueno.Name)); no se tocó"
    }
}
