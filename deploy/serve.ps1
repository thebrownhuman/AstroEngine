# Run the engine and expose it through Cloudflare Tunnel.
#
#   .\deploy\serve.ps1              # local only, http://127.0.0.1:8000
#   .\deploy\serve.ps1 -Tunnel      # also start the tunnel
#
# The engine binds to loopback only, so the tunnel is the only way in from
# outside. Put Cloudflare Access in front of the hostname if you want auth
# without writing any.

param(
    [switch]$Tunnel,
    [string]$TunnelName = "astro",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Use the real Swiss Ephemeris files when they are present.
$ephe = Join-Path $root "ephe"
if (Test-Path $ephe) {
    $env:SE_EPHE_PATH = $ephe
    Write-Host "ephemeris: swieph ($ephe)" -ForegroundColor Green
} else {
    Write-Host "ephemeris: moshier (no .se1 files found; see README)" -ForegroundColor Yellow
}

if (-not (Test-Path (Join-Path $root "data\places.sqlite"))) {
    Write-Host "place index missing - building it now..." -ForegroundColor Yellow
    & (Join-Path $root ".venv\Scripts\python.exe") -m astro_engine.places build
}

if ($Tunnel) {
    Write-Host "starting cloudflared tunnel '$TunnelName'..." -ForegroundColor Cyan
    Start-Process cloudflared -ArgumentList "tunnel","run",$TunnelName
}

& (Join-Path $root ".venv\Scripts\uvicorn.exe") astro_engine.api:app `
    --host 127.0.0.1 --port $Port
