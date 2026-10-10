<#
.SYNOPSIS
  Quita el arranque automático de la copia diaria (tarea programada o acceso directo).
  No detiene la oficina si está corriendo (para eso: detener-oficina.ps1).
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

$quitado = $false
if (Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
    Write-Host "Tarea programada '$NombreTarea' eliminada."
    $quitado = $true
}
$acceso = Join-Path ([Environment]::GetFolderPath('Startup')) "$NombreTarea.lnk"
if (Test-Path $acceso) {
    Remove-Item -Force $acceso
    Write-Host "Acceso directo de Inicio eliminado: $acceso"
    $quitado = $true
}
if (-not $quitado) { Write-Host "No había arranque automático instalado." }
