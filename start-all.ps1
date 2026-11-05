<#
  SentinelAI - launch backend + frontend together (Windows / PowerShell).

  Usage (from the project root):
      powershell -ExecutionPolicy Bypass -File .\start-all.ps1

  First run installs dependencies (Python venv + npm). Later runs skip install,
  but auto-refresh backend packages if pyproject.toml changed.
  Backend uses a local SQLite database (dev.db) so no Postgres is required.
  A default account is seeded:  admin@sentinelai.app / admin12345
#>

$ErrorActionPreference = "Stop"
$root     = $PSScriptRoot
$backend  = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "Starting SentinelAI..." -ForegroundColor Cyan

# --- Backend: venv + install/refresh, migrate, seed, run uvicorn (SQLite) ---
$backendCmd = @"
Set-Location '$backend'
if (-not (Test-Path '.venv')) {
  Write-Host 'Setting up backend (one-time)...' -ForegroundColor Yellow
  python -m venv .venv
  .\.venv\Scripts\python.exe -m pip install --upgrade pip
  .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
  Copy-Item pyproject.toml .venv\deps.stamp -Force
}
elseif ((-not (Test-Path '.venv\deps.stamp')) -or ((Get-FileHash pyproject.toml).Hash -ne (Get-FileHash .venv\deps.stamp).Hash)) {
  Write-Host 'Dependencies changed; updating backend packages...' -ForegroundColor Yellow
  .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
  Copy-Item pyproject.toml .venv\deps.stamp -Force
}
`$env:DATABASE_URL = 'sqlite+pysqlite:///./dev.db'
`$env:STORAGE_DIR  = './var/uploads'
Write-Host 'Applying database migrations...' -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m alembic upgrade head
Write-Host 'Seeding default account (admin@sentinelai.app / admin12345)...' -ForegroundColor Yellow
.\.venv\Scripts\python.exe -m app.seed
Write-Host 'Backend running at http://localhost:8000  (API docs: /docs)' -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
"@

# --- Frontend: npm install on first run, then dev server ---
$frontendCmd = @"
Set-Location '$frontend'
if (-not (Test-Path 'node_modules')) {
  Write-Host 'Installing frontend dependencies (one-time)...' -ForegroundColor Yellow
  npm install
}
Write-Host 'Frontend running at http://localhost:3000' -ForegroundColor Green
npm run dev
"@

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "Two windows opened. Login: admin@sentinelai.app / admin12345" -ForegroundColor Cyan
Write-Host "  Backend  -> http://localhost:8000" -ForegroundColor Green
Write-Host "  Frontend -> http://localhost:3000" -ForegroundColor Green
