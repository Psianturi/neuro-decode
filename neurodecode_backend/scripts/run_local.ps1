param(
  [int]$Port = 8000,
  [string]$HostAddr = "0.0.0.0"
)

$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
  throw "Venv not found at $pythonExe. Create it first: python -m venv .venv (from $backendRoot)"
}

Push-Location $backendRoot
try {
  & $pythonExe -m uvicorn app.main:app --host $HostAddr --port $Port --reload
} finally {
  Pop-Location
}
