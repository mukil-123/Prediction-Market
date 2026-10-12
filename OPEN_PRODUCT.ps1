$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'

$alphaUrl = 'https://github.com/mukil-123/Prediction-Market/archive/refs/heads/alpha-shadow-20261012.zip'
$alphaId = [Guid]::NewGuid().ToString('N').Substring(0,8)
$alphaZip = Join-Path $env:TEMP "PMA-$alphaId.zip"
$alphaFolder = Join-Path $env:USERPROFILE "PMA-$alphaId"

Write-Host 'Downloading Prediction Market Alpha...'
try {
    Invoke-WebRequest -UseBasicParsing -Uri $alphaUrl -OutFile $alphaZip
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $alphaCheck = [IO.Compression.ZipFile]::OpenRead($alphaZip)
    $alphaCheck.Dispose()
} catch {
    Start-Process 'https://github.com/mukil-123/Prediction-Market/tree/alpha-shadow-20261012'
    Add-Type -AssemblyName System.Windows.Forms
    [void][Windows.Forms.MessageBox]::Show('In GitHub, sign in if needed, then click Code > Download ZIP. Click OK here after downloading.','Download the product')
    $alphaPick = New-Object Windows.Forms.OpenFileDialog
    $alphaPick.Filter = 'ZIP files (*.zip)|*.zip'
    $alphaPick.InitialDirectory = Join-Path $env:USERPROFILE 'Downloads'
    $alphaPick.Title = 'Select the Prediction-Market-alpha-shadow-20261012 ZIP'
    if ($alphaPick.ShowDialog() -ne [Windows.Forms.DialogResult]::OK) { throw 'No ZIP selected.' }
    $alphaZip = $alphaPick.FileName
}

Expand-Archive -LiteralPath $alphaZip -DestinationPath $alphaFolder
$alphaRoot = (Get-ChildItem -LiteralPath $alphaFolder -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName 'CONTINUATION_RELEASE.json')
} | Select-Object -First 1).FullName
if (-not $alphaRoot) { throw 'Select the updated project ZIP from the alpha-shadow-20261012 branch.' }
$alphaFrozen = Join-Path $alphaRoot 'data\cohorts\PM-C1-FORWARD-003.json'
if ((Get-FileHash -LiteralPath $alphaFrozen -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'cc9f69d812d99b80d120c1e63a54287d85dc776bb0645c57f2e5899a5830e3d0') {
    throw 'Frozen research checksum failed. Nothing was launched.'
}

$alphaPython = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        $alphaCandidate = & py -3 -c "import sys; print(sys.executable if sys.version_info >= (3,11) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $alphaCandidate -and (Test-Path -LiteralPath $alphaCandidate)) { $alphaPython = $alphaCandidate }
    } catch {}
}
if (-not $alphaPython) {
    foreach ($alphaVersion in @('314','313','312','311')) {
        $alphaCandidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$alphaVersion\python.exe"
        if (Test-Path -LiteralPath $alphaCandidate) { $alphaPython = $alphaCandidate; break }
    }
}
if (-not $alphaPython) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11+ from python.org, then run this block again.' }
    Write-Host 'Installing free Python 3.12...'
    & winget install --id Python.Python.3.12 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Python installation did not complete.' }
    $alphaPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
}
if (-not (Test-Path -LiteralPath $alphaPython)) { throw 'Python was not found after installation.' }

Set-Location -LiteralPath $alphaRoot
& $alphaPython -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python environment setup failed.' }
$alphaVenv = Join-Path $alphaRoot '.venv\Scripts\python.exe'
& $alphaVenv -m pip install --disable-pip-version-check tzdata
if ($LASTEXITCODE -ne 0) { throw 'Timezone-data installation failed.' }
$env:PYTHONPATH = Join-Path $alphaRoot 'src'
$env:LIVE_TRADING = 'false'
$alphaPort = & $alphaVenv -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()"
if ($LASTEXITCODE -ne 0) { throw 'Could not select a local port.' }

Write-Host "Project saved in: $alphaRoot"
Write-Host 'Opening the product. Keep this PowerShell window open. Ctrl+C stops it.'
& $alphaVenv -m pm_alpha --root $alphaRoot research-loop --no-collect --port $alphaPort --open-browser
