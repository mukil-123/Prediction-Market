# Run from the repository root, with the documented virtual environment installed.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Push-Location $ProjectRoot
try {
    & $ProjectPython -m pm_alpha shadow-once --limit 10
    if ($LASTEXITCODE -ne 0) { throw "Shadow collection failed; no success assumed." }
    & $ProjectPython -m pm_alpha daily-report
    if ($LASTEXITCODE -ne 0) { throw "Daily report failed." }
} finally {
    Pop-Location
}
