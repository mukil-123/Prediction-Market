$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$StopFile = Join-Path $ProjectRoot "data\STOP_COLLECTOR"
New-Item $StopFile -ItemType File -Force | Out-Null
Write-Output "Clean stop requested. Collection finishes its bounded current request/cycle."
