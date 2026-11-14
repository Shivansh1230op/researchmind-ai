param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot 'venv\Scripts\python.exe'
$webPath = Join-Path $projectRoot 'web'
$logPath = Join-Path $projectRoot '.researchmind-logs'

function Test-Endpoint([string]$Address) {
    try { return (Invoke-WebRequest -Uri $Address -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 }
    catch { return $false }
}

try {
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python environment missing. Follow docs/QUICKSTART.md to install dependencies first.' }
    $nodePath = (Get-Command node -ErrorAction Stop).Source
    if (-not (Test-Path -LiteralPath (Join-Path $webPath '.next\BUILD_ID'))) { throw 'Frontend build missing. Run npm.cmd run build inside web first.' }
    New-Item -ItemType Directory -Path $logPath -Force | Out-Null
    $env:DEBUG = 'false'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    if (-not (Test-Endpoint 'http://127.0.0.1:8000/ready')) {
        Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'backend.log') -RedirectStandardError (Join-Path $logPath 'backend-error.log') | Out-Null
    }
    if (-not (Test-Endpoint 'http://localhost:3000/login')) {
        Start-Process -FilePath $nodePath -ArgumentList @('node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','3000') -WorkingDirectory $webPath -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logPath 'web.log') -RedirectStandardError (Join-Path $logPath 'web-error.log') | Out-Null
    }
    $deadline = (Get-Date).AddSeconds(60)
    do {
        $ready = (Test-Endpoint 'http://localhost:3000/login') -and (Test-Endpoint 'http://localhost:3000/api/ready')
        if ($ready) { break }
        Start-Sleep -Milliseconds 750
    } while ((Get-Date) -lt $deadline)
    if (-not $ready) { throw "App did not start. See logs in $logPath. Ports 3000 and 8000 must be available." }
    Write-Host 'ResearchMind is ready: http://localhost:3000/login'
    if (-not $NoBrowser) { Start-Process 'http://localhost:3000/login' }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $NoBrowser) { Read-Host 'Press Enter to close' | Out-Null }
    exit 1
}
