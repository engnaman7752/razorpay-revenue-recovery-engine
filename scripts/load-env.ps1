<#
  Loads .env into the CURRENT PowerShell session.

  Spring Boot and uvicorn do not read .env files themselves — only Docker
  Compose does. Run this once per terminal before starting a service by hand.

  Usage (note the leading dot — it must be dot-sourced to persist):
      . .\scripts\load-env.ps1
#>
param([string]$Path)

if (-not $Path) { $Path = Join-Path (Split-Path $PSScriptRoot -Parent) ".env" }

if (-not (Test-Path $Path)) {
    Write-Host "No .env found at $Path" -ForegroundColor Red
    Write-Host "Create it first:  copy env.local.txt .env" -ForegroundColor Yellow
    return
}

$loaded = 0
Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $i = $line.IndexOf("=")
    if ($i -lt 1) { return }
    $name  = $line.Substring(0, $i).Trim()
    $value = $line.Substring($i + 1).Trim().Trim('"')
    [Environment]::SetEnvironmentVariable($name, $value, "Process")
    $loaded++
}

Write-Host "Loaded $loaded variables from $Path" -ForegroundColor Green
Write-Host ("  DATABASE_URL   = " + $env:DATABASE_URL)
Write-Host ("  DATABASE_USER  = " + $env:DATABASE_USER)
Write-Host ("  GATEWAY_MODE   = " + $env:GATEWAY_MODE)
$g = if ($env:GOOGLE_API_KEY) { "set (" + $env:GOOGLE_API_KEY.Substring(0,6) + "...)" } else { "NOT set - agent uses rule fallback" }
Write-Host ("  GOOGLE_API_KEY = " + $g)
