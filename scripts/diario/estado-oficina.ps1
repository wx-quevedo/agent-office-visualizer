<#
.SYNOPSIS
  Dice si la copia diaria está corriendo, en qué commit está y si los puertos responden.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

Write-Host "Oficina de agentes (copia diaria) - estado"
Write-Host "  Copia:   $Raiz"
if (Test-Path (Join-Path $Raiz '.git')) {
    $commit = & git -C $Raiz log -1 --format='%h %s (%cr)' 2>$null
    $rama = & git -C $Raiz rev-parse --abbrev-ref HEAD 2>$null
    Write-Host "  Commit:  $commit [rama $rama]"
} else {
    Write-Host "  Commit:  (no hay copia en $Raiz)" -ForegroundColor Yellow
}
Write-Host "  Datos:   $Datos"
Write-Host "  Logs:    $Logs"

$procesos = @(Get-ProcesosDiario | Where-Object { $_.Name -ne 'cmd.exe' })
Write-Host "  Procesos de la copia diaria: $($procesos.Count)"
foreach ($puerto in @($PuertoBackend, $PuertoFrontend)) {
    $dueno = Get-DuenoPuerto $puerto
    $quien = if (-not $dueno) { 'libre' } elseif (Test-ComandoDiario $dueno.CommandLine) { "copia diaria (PID $($dueno.ProcessId))" } else { "OTRO programa (PID $($dueno.ProcessId), $($dueno.Name))" }
    Write-Host "  Puerto ${puerto}: $quien"
}
$salud = Test-Url "http://127.0.0.1:$PuertoBackend/health"
$pagina = Test-Url "http://127.0.0.1:$PuertoFrontend/oficina"
$estado = Test-Url "http://127.0.0.1:$PuertoBackend/api/v1/agents/state"
Write-Host "  Backend  /health:              $(if ($salud) { $salud } else { 'no responde' })"
Write-Host "  Backend  /api/v1/agents/state: $(if ($estado) { $estado } else { 'no responde' })"
Write-Host "  Frontend /oficina:             $(if ($pagina) { $pagina } else { 'no responde' })"
$tarea = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
$acceso = Join-Path ([Environment]::GetFolderPath('Startup')) "$NombreTarea.lnk"
$arranque = if ($tarea) { "tarea programada '$NombreTarea'" } elseif (Test-Path $acceso) { "acceso directo en Inicio" } else { 'no instalado' }
Write-Host "  Arranque automático: $arranque"
if ($salud -eq 200 -and $pagina -eq 200) { Write-Host "Corriendo." -ForegroundColor Green } else { Write-Host "No está corriendo completa." -ForegroundColor Yellow }
