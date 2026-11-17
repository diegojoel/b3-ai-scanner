$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\frontend"

if (-not (Test-Path "node_modules")) {
    npm install
}

$env:VITE_API_URL = if ($env:VITE_API_URL) { $env:VITE_API_URL } else { "http://localhost:8000" }
npm run dev -- --host 127.0.0.1 --port 5173

