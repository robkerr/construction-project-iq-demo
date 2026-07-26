<#
.SYNOPSIS
    Verify/install prerequisites for the Contoso E&C Project-Intelligence Fabric demo.
    - checks Python + Azure CLI (+ login)
    - installs the Fabric CLI (fab) via pip if missing
    - creates a Python venv and installs the data-generation deps
.NOTES
    Idempotent. Safe to re-run. Only lightweight, cross-platform deps are installed here;
    the Lakehouse medallion build runs in Fabric notebooks (see fabric/notebooks).
#>
[CmdletBinding()]
param([switch]$SkipVenv)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$root = Get-RepoRoot

Write-Host '== Checking Python ==' -ForegroundColor Cyan
Assert-Command python 'Install Python 3.11+ from https://www.python.org/downloads/'
Write-Host "  $(python --version)"

Write-Host '== Checking Azure CLI ==' -ForegroundColor Cyan
if (Get-Command az -ErrorAction SilentlyContinue) {
    $acct = az account show 2>$null | ConvertFrom-Json
    if ($acct) { Write-Host "  Signed in as $($acct.user.name) (sub: $($acct.name))" }
    else { Write-Warning "  Azure CLI present but not logged in. Run 'az login' before setup_spn.ps1." }
} else {
    Write-Warning "  Azure CLI not found. Install: https://learn.microsoft.com/cli/azure/install-azure-cli"
}

Write-Host '== Checking Fabric CLI (fab) ==' -ForegroundColor Cyan
if (-not (Get-Command fab -ErrorAction SilentlyContinue)) {
    Write-Host '  Installing ms-fabric-cli via pip...'
    python -m pip install --upgrade pip | Out-Null
    python -m pip install ms-fabric-cli
} else { Write-Host "  $(fab --version 2>$null)" }

if (-not $SkipVenv) {
    Write-Host '== Creating Python venv + installing data-generation deps ==' -ForegroundColor Cyan
    $venv = Join-Path $root '.venv'
    if (-not (Test-Path $venv)) { python -m venv $venv }
    $pip = Join-Path $venv 'Scripts\pip.exe'
    & $pip install --upgrade pip | Out-Null
    $req = Join-Path $root 'data_gen\requirements.txt'
    if (Test-Path $req) { & $pip install -r $req }
    Write-Host "  venv ready at $venv"
    Write-Host "  Activate it before running python:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Prerequisites checked. Next:' -ForegroundColor Green
Write-Host '  1) .\.venv\Scripts\Activate.ps1'
Write-Host '  2) python .\data_gen\generate.py            # synthetic SAP + non-SAP data'
Write-Host '  3) python .\data_gen\docs_gen.py            # unstructured corpus for AI Search'
Write-Host '  4) az login; .\scripts\setup_spn.ps1        # provision Fabric access'
