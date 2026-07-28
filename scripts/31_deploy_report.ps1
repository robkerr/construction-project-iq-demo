<#
.SYNOPSIS
    Deploy the "Portfolio Schedule Risk" Power BI report (Phase 5) to the Fabric workspace.

.DESCRIPTION
    Reads the PBIR definition folder produced by powerbi/build_report.py, base64-encodes every
    part (excluding .platform), and creates (or updates, if it already exists) the report in the
    workspace via the Fabric REST API. The report binds byConnection to the ProjectControlsIQ
    semantic model, so the model must be deployed first (scripts/30_deploy_semantic_model.ps1).
    Writes REPORT_ID / REPORT_NAME back to .env.

.NOTES
    The report is owned by the identity that creates it. Because the semantic model was authored
    by the signed-in user, deploy the report as the same user (-Auth user) for a clean binding.
#>
[CmdletBinding()]
param(
    [string]$ReportName = 'ProjectControlsIQ',
    [string]$DefinitionRoot,
    [string]$ReportIdKey = 'REPORT_ID',
    [string]$ReportNameKey = 'REPORT_NAME',
    [ValidateSet('auto', 'user', 'spn')]
    [string]$Auth = 'auto'
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$env = Import-DotEnv

$ws = $env.FABRIC_WORKSPACE_ID
if (-not $ws) { throw 'FABRIC_WORKSPACE_ID not set in .env.' }
if (-not $env.SEMANTIC_MODEL_ID) { throw 'SEMANTIC_MODEL_ID not set in .env. Deploy the semantic model first (30_deploy_semantic_model.ps1).' }
if (-not $DefinitionRoot) {
    $DefinitionRoot = Join-Path (Get-RepoRoot) "powerbi\$ReportName.Report"
}
if (-not (Test-Path $DefinitionRoot)) {
    throw "Definition folder not found: $DefinitionRoot. Run powerbi/build_report.py first."
}

$spnAvailable = [bool]($env.SPN_APP_ID -and $env.SPN_CLIENT_SECRET -and $env.SPN_TENANT_ID)
switch ($Auth) {
    'user' { $useSpn = $false }
    'spn' { if (-not $spnAvailable) { throw 'Auth=spn requested but SPN_* creds are not in .env.' }; $useSpn = $true }
    default { $useSpn = $spnAvailable }
}
Write-Host ("Auth: " + $(if ($useSpn) { "service principal ($($env.SPN_DISPLAY_NAME))" } else { 'signed-in Azure CLI user' })) -ForegroundColor DarkCyan
$token = Get-FabricToken -UseSpn:$useSpn

# --- Build the parts array from the definition folder (exclude .platform) ---
$root = (Resolve-Path $DefinitionRoot).Path
$files = Get-ChildItem -Path $root -Recurse -File | Where-Object { $_.Name -ne '.platform' }
$parts = foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length + 1) -replace '\\', '/'
    $b64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($f.FullName))
    @{ path = $rel; payload = $b64; payloadType = 'InlineBase64' }
}
Write-Host "== Deploying report '$ReportName' ($($parts.Count) parts) ==" -ForegroundColor Cyan

# --- Does a report with this name already exist? ---
$existing = (Invoke-FabricApi -Method GET -Path "/workspaces/$ws/reports" -Token $token).value |
    Where-Object { $_.displayName -eq $ReportName } | Select-Object -First 1

if ($existing) {
    Write-Host "  Updating existing report (id=$($existing.id))"
    $body = @{ definition = @{ parts = $parts } }
    Invoke-FabricLro -Path "/workspaces/$ws/reports/$($existing.id)/updateDefinition" -Body $body -Token $token | Out-Null
    $reportId = $existing.id
}
else {
    Write-Host "  Creating new report"
    $body = @{ displayName = $ReportName; definition = @{ parts = $parts } }
    Invoke-FabricLro -Path "/workspaces/$ws/reports" -Body $body -Token $token | Out-Null
    Start-Sleep -Seconds 3
    $reportId = ((Invoke-FabricApi -Method GET -Path "/workspaces/$ws/reports" -Token $token).value |
        Where-Object { $_.displayName -eq $ReportName } | Select-Object -First 1).id
}

if (-not $reportId) { throw "Deployment reported success but the report could not be found by name." }
Set-DotEnvValue -Key $ReportIdKey -Value $reportId
Set-DotEnvValue -Key $ReportNameKey -Value $ReportName

Write-Host ''
Write-Host "Report deployed. id=$reportId" -ForegroundColor Green
Write-Host "Open it: https://app.fabric.microsoft.com/groups/$ws/reports/$reportId" -ForegroundColor Green
