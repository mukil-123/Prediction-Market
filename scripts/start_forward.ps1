# Local foreground loop. No hosting, credentials, trading or execution-policy changes.
param([int]$Seconds = 0)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Push-Location $ProjectRoot
try {
    if (-not (Test-Path $ProjectPython)) { throw "Create the documented .venv first." }
    & $ProjectPython -c "from zoneinfo import ZoneInfo; print(ZoneInfo('America/New_York'))"
    if ($LASTEXITCODE -ne 0) { throw "IANA timezone data missing. Supply free tzdata or PYTHONTZPATH; no UTC-offset guess is allowed." }
    if (Test-Path "data\STOP_COLLECTOR") { Remove-Item "data\STOP_COLLECTOR" }
    & $ProjectPython -m pm_alpha freeze-forward
    if ($LASTEXITCODE -ne 0) { throw "Cohort freeze failed." }
    if ($Seconds -gt 0) { & $ProjectPython -u -m pm_alpha collect-forward --seconds $Seconds }
    else { & $ProjectPython -u -m pm_alpha collect-forward }
    if ($LASTEXITCODE -ne 0) { throw "Collector stopped with an error; inspect data\collector_health.json and daily report." }
} finally { Pop-Location }
