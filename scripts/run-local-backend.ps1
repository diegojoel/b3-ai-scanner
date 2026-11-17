$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./scanner.local.db" }
$env:CORS_ORIGINS = if ($env:CORS_ORIGINS) { $env:CORS_ORIGINS } else { "http://localhost:5173,http://127.0.0.1:5173" }
$env:SEED_DEMO_DATA = if ($env:SEED_DEMO_DATA) { $env:SEED_DEMO_DATA } else { "true" }
$env:CREATE_DB_ON_STARTUP = if ($env:CREATE_DB_ON_STARTUP) { $env:CREATE_DB_ON_STARTUP } else { "true" }

$Python312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
$Python = if (Test-Path $Python312) { $Python312 } else { "python" }

if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
