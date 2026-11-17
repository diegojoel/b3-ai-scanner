$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$env:DATABASE_URL = "sqlite:///./scanner.local.db"
$env:USE_REAL_MARKET_DATA = "true"
$env:SCAN_ALL_B3 = "true"
$env:SEED_DEMO_DATA = "true"
$env:CREATE_DB_ON_STARTUP = "true"

& "$projectRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
