<# 
.SYNOPSIS
    agentik quick-start script for Windows.

.DESCRIPTION
    Builds the Docker image (if needed) and starts the web UI.

.EXAMPLE
    .\scripts\start.ps1                 # web UI (default)
    .\scripts\start.ps1 --pipeline      # interactive pipeline mode
    .\scripts\start.ps1 --build-only    # just build the image
#>
param(
    [Parameter(Position = 0, ValueFromRemainingArguments)]
    [string[]]$Args
)

$ErrorActionPreference = "Continue"   # don't auto-close on non-terminating errors
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$ComposeFile = Join-Path $ProjectRoot "docker-compose.yml"

Set-Location $ProjectRoot

function Info($msg)  { Write-Host "▸ $msg" -ForegroundColor Blue }
function Ok($msg)    { Write-Host "✔ $msg" -ForegroundColor Green }
function Die($msg) {
    Write-Host "`n✗ $msg" -ForegroundColor Red
    Write-Host "Press Enter to close..." -ForegroundColor Red
    $null = Read-Host
    exit 1
}

# Check Docker is available.
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Die "Docker is not installed. Get it at https://docs.docker.com/get-docker/"
}

# Ensure .env exists.
if (-not (Test-Path .env)) {
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Info "Created .env from .env.example — edit it with your API keys."
    } else {
        Info "No .env file found. Create one with your API keys (see .env.example)."
    }
}

# Ensure projects directory exists.
if (-not (Test-Path projects)) { New-Item -ItemType Directory projects | Out-Null }

$Mode = if ($Args.Count -gt 0) { $Args[0] } else { "" }

switch ($Mode) {
    "--build-only" {
        Info "Building Docker image..."
        docker compose -f $ComposeFile build
        Ok "Image built successfully."
    }
    "--pipeline" {
        Info "Starting agentik pipeline (interactive)..."
        docker compose -f $ComposeFile run --rm agentik --pipeline
    }
    { $_ -in "--detach", "-d" } {
        Info "Starting agentik web UI (detached)..."
        docker compose -f $ComposeFile up -d --build
        $port = if ($env:AGENTIK_PORT) { $env:AGENTIK_PORT } else { "8420" }
        Ok "Web UI running at http://localhost:$port"
    }
    { $_ -in "--down", "--stop" } {
        Info "Stopping agentik..."
        docker compose -f $ComposeFile down
        Ok "Stopped."
    }
    { $_ -in "", "--web" } {
        Info "Starting agentik web UI..."
        docker compose -f $ComposeFile up --build
    }
    default {
        Info "Passing arguments to agentik: $($Args -join ' ')"
        docker compose -f $ComposeFile run --rm agentik @Args
    }
}
# If launched in its own window (e.g. double-clicked), keep it open so the user
# can read output before it disappears.
try {
    $parent = (Get-Process -Id (Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction SilentlyContinue).ParentProcessId -ErrorAction SilentlyContinue).Name
    if (-not $parent -or $parent -match 'explorer|winfile') {
        Write-Host ""
        Write-Host "Press Enter to close..." -ForegroundColor DarkGray
        $null = Read-Host
    }
} catch {
    # Not critical.
}
