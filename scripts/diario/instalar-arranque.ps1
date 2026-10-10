<#
.SYNOPSIS
  Hace que la copia diaria arranque sola al iniciar sesión en Windows.

.DESCRIPTION
  Crea una tarea programada del usuario actual (al iniciar sesión, sin permisos
  de administrador, nivel normal) que corre iniciar-oficina.ps1 de la copia
  diaria sin ventana. Si Windows no permite crear la tarea sin administrador,
  crea en su lugar un acceso directo en la carpeta Inicio del usuario.
  Se deshace con quitar-arranque.ps1.
#>
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\comun.ps1"

$script = Join-Path $Raiz 'scripts\diario\iniciar-oficina.ps1'
if (-not (Test-Path $script)) { throw "No existe $script (prepara primero la copia diaria)." }
$argumentos = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$usuario = "$env:USERDOMAIN\$env:USERNAME"

try {
    $accion = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argumentos -WorkingDirectory $Raiz
    $disparador = New-ScheduledTaskTrigger -AtLogOn -User $usuario
    $principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
    $ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
    Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $disparador -Principal $principal -Settings $ajustes `
        -Description 'Arranca la oficina de agentes (copia diaria, puertos 3000/8000) al iniciar sesión.' -Force | Out-Null
    Write-Host "Tarea programada '$NombreTarea' creada: la oficina diaria arrancará al iniciar sesión."
} catch {
    Write-Host "No se pudo crear la tarea programada sin administrador ($($_.Exception.Message))." -ForegroundColor Yellow
    $acceso = Join-Path ([Environment]::GetFolderPath('Startup')) "$NombreTarea.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($acceso)
    $lnk.TargetPath = 'powershell.exe'
    $lnk.Arguments = $argumentos
    $lnk.WorkingDirectory = $Raiz
    $lnk.WindowStyle = 7
    $lnk.Description = 'Arranca la oficina de agentes (copia diaria) al iniciar sesión.'
    $lnk.Save()
    Write-Host "En su lugar se creó un acceso directo en Inicio: $acceso"
}
