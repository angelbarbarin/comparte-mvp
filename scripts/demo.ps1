# Arranca la demo de ComParte en Windows (PowerShell).
#
#   .\scripts\demo.ps1                 # hora de demo 16:00, datos recién cargados, puerto 8000
#   .\scripts\demo.ps1 -Hora 15:30 -Puerto 8080
#
# Crea el entorno virtual si no existe, instala dependencias, recarga los datos de prueba, fija la hora
# de la aplicación (el video no depende de la hora real) y arranca el servidor.
# Si la carpeta está en OneDrive, define $env:COMPARTE_VENV con una ruta fuera de OneDrive.

param([string]$Hora = "16:00", [int]$Puerto = 8000)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$venv = if ($env:COMPARTE_VENV) { $env:COMPARTE_VENV } else { ".venv" }
if (-not (Test-Path $venv)) { python -m venv $venv }
$python = Join-Path $venv "Scripts\python.exe"
& $python -m pip install --quiet -r requirements.txt

Write-Host "Abre http://127.0.0.1:$Puerto  (Ctrl+C para detener)"
& $python -m comparte --puerto $Puerto --hora-demo $Hora --reiniciar
