# PDV Lumina — sobe mock-sefaz + API + frontend juntos.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\run_dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "== PDV Lumina dev ==" -ForegroundColor Green

# 1) mock-sefaz (porta 3000)
if (Test-Path "$root\mock-sefaz\server.js") {
  Write-Host "[1/3] mock-sefaz :3000..."
  Start-Process -FilePath "node" -ArgumentList "server.js" -WorkingDirectory "$root\mock-sefaz" -WindowStyle Minimized
}

# 2) API FastAPI (porta 8000)
Write-Host "[2/3] API :8000..."
Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "src.api.app:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory $root -WindowStyle Minimized

# 3) frontend Vite (porta 5173)
Write-Host "[3/3] frontend :5173..."
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
