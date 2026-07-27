<#
.SYNOPSIS
    Run the medallion notebooks in order against the Project-Intelligence Lakehouse.

.DESCRIPTION
    Runs 01 -> 02 -> 03 via the Fabric "RunNotebook" job API, attaching the Lakehouse as
    the default lakehouse, and polls each job to completion. Builds bronze/silver/gold and
    the gold.project_schedule_risk table the semantic model + agent read from.

.NOTES
    Requires 10_provision_fabric.ps1 to have run (notebooks imported, FABRIC_LAKEHOUSE_ID set).
#>
[CmdletBinding()]
param([string[]]$Only)   # optional subset, e.g. -Only 03_build_silver_gold
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$env = Import-DotEnv

$ws = $env.FABRIC_WORKSPACE_ID
$lakehouseId = $env.FABRIC_LAKEHOUSE_ID
$lhName = if ($env.FABRIC_LAKEHOUSE_NAME) { $env.FABRIC_LAKEHOUSE_NAME } else { 'lh_project_intelligence' }
if (-not $lakehouseId) { throw "FABRIC_LAKEHOUSE_ID not set. Run 10_provision_fabric.ps1 first." }
$apiBase = if ($env.FABRIC_API_BASE) { $env.FABRIC_API_BASE } else { 'https://api.fabric.microsoft.com/v1' }

# Use the service principal when .env carries SPN creds; otherwise fall back to the signed-in az user.
$useSpn = [bool]($env.SPN_APP_ID -and $env.SPN_CLIENT_SECRET -and $env.SPN_TENANT_ID)
Write-Host ("Auth: " + $(if ($useSpn) { "service principal ($($env.SPN_DISPLAY_NAME))" } else { 'signed-in Azure CLI user' })) -ForegroundColor DarkCyan

$token = Get-FabricToken -UseSpn:$useSpn
$order = @('01_setup_lakehouse', '02_load_bronze', '03_build_silver_gold')
if ($Only) { $order = $order | Where-Object { $Only -contains $_ } }

$notebooks = (Invoke-FabricApi -Method GET -Path "/workspaces/$ws/notebooks" -Token $token).value

foreach ($name in $order) {
    $nb = $notebooks | Where-Object { $_.displayName -eq $name } | Select-Object -First 1
    if (-not $nb) { throw "Notebook '$name' not found in workspace. Re-run 10_provision_fabric.ps1." }

    Write-Host "== Running $name ==" -ForegroundColor Cyan
    # defaultLakehouse MUST be nested under executionData.configuration (not directly under
    # executionData) or Fabric ignores it and relative Files/ paths won't resolve.
    $body = @{
        executionData = @{
            configuration = @{
                defaultLakehouse = @{ name = $lhName; id = $lakehouseId; workspaceId = $ws }
                useStarterPool   = $true
            }
        }
    }
    $uri = "$apiBase/workspaces/$ws/items/$($nb.id)/jobs/instances?jobType=RunNotebook"
    $resp = Invoke-WebRequest -Method Post -Uri $uri -Headers @{ Authorization = "Bearer $token" } `
        -Body ($body | ConvertTo-Json -Depth 10) -ContentType 'application/json' -UseBasicParsing
    $statusUrl = @($resp.Headers['Location'])[0]
    if (-not $statusUrl) { throw "No job status URL returned for $name." }

    $deadline = (Get-Date).AddSeconds(1800)
    do {
        Start-Sleep -Seconds 10
        $job = Invoke-RestMethod -Method Get -Uri $statusUrl -Headers @{ Authorization = "Bearer $token" }
        Write-Host "  status: $($job.status)"
        if ((Get-Date) -gt $deadline) { throw "  $name timed out." }
    } while ($job.status -in @('NotStarted', 'InProgress', 'Running'))

    if ($job.status -ne 'Completed') {
        throw "  $name did not complete (status=$($job.status)): $($job.failureReason.message)"
    }
    Write-Host "  $name completed." -ForegroundColor Green
    $token = Get-FabricToken -UseSpn:$useSpn   # refresh in case of long total runtime
    $notebooks = (Invoke-FabricApi -Method GET -Path "/workspaces/$ws/notebooks" -Token $token).value
}

Write-Host ''
Write-Host 'Data load complete. bronze/silver/gold + gold.project_schedule_risk are built.' -ForegroundColor Green
Write-Host 'Next:' -ForegroundColor Green
Write-Host '  1) Build the Power BI semantic model (fabric/semantic-model + fabric/measures.dax).'
Write-Host '  2) Build the Azure AI Search index (search/build_index.md).'
Write-Host '  3) Build the Foundry / M365 Copilot agent (agent/).'
