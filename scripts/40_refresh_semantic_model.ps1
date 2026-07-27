<#
.SYNOPSIS
    Refresh (frame) the ProjectControlsIQ Direct Lake semantic model so it is queryable.

.DESCRIPTION
    A freshly deployed Direct Lake model must be "framed" before its first query, otherwise
    DAX returns "TABLE ... is not refreshed and fallback to DirectQuery is disabled". This script
    triggers a Power BI enhanced refresh (type=full) via the Power BI REST API and polls to
    completion. Re-run it after reloading the Lakehouse silver tables so the model picks up new data.

.NOTES
    Uses the signed-in Azure CLI user by default (the model author). Power BI audience:
    https://analysis.windows.net/powerbi/api. Adding measures does NOT require a refresh (metadata
    only); a refresh is needed after (re)deploying tables or reloading the underlying data.
#>
[CmdletBinding()]
param(
    [string]$DatasetId,
    [int]$TimeoutSeconds = 300
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$env = Import-DotEnv

$ws = $env.FABRIC_WORKSPACE_ID
if (-not $ws) { throw 'FABRIC_WORKSPACE_ID not set in .env.' }
if (-not $DatasetId) { $DatasetId = $env.SEMANTIC_MODEL_ID }
if (-not $DatasetId) { throw 'SEMANTIC_MODEL_ID not set in .env (deploy the model first).' }

Assert-Command az 'Install the Azure CLI.'
$pbiTok = az account get-access-token --resource 'https://analysis.windows.net/powerbi/api' --query accessToken -o tsv
if (-not $pbiTok) { throw 'Failed to obtain a Power BI token.' }
$hdr = @{ Authorization = "Bearer $pbiTok" }
$uri = "https://api.powerbi.com/v1.0/myorg/groups/$ws/datasets/$DatasetId/refreshes"

Write-Host "== Refreshing (framing) Direct Lake model $DatasetId ==" -ForegroundColor Cyan
Invoke-WebRequest -Method Post -Uri $uri -Headers $hdr -Body (@{ type = 'full' } | ConvertTo-Json) `
    -ContentType 'application/json' -UseBasicParsing | Out-Null

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Seconds 4
    $last = (Invoke-RestMethod -Method Get -Uri "$uri`?`$top=1" -Headers $hdr).value | Select-Object -First 1
    Write-Host "  status: $($last.status)"
} while ($last.status -in 'Unknown', 'InProgress' -and (Get-Date) -lt $deadline)

if ($last.status -eq 'Completed') {
    Write-Host "Refresh completed. Model is framed and queryable." -ForegroundColor Green
}
else {
    Write-Warning "Refresh ended with status '$($last.status)'. Details: $($last.serviceExceptionJson)"
}
