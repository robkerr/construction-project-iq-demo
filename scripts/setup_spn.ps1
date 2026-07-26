<#
.SYNOPSIS
    Create a service principal for the demo and grant it Admin on the Fabric workspace.

.DESCRIPTION
    Uses the Azure CLI to:
      1. create (or reuse) an Entra app registration + service principal
      2. create a client secret
      3. grant the SPN the 'Admin' role on the target Fabric workspace (Fabric REST API)
    Writes SPN_APP_ID / SPN_CLIENT_SECRET / SPN_TENANT_ID to .env.

.NOTES
    Idempotent: reuses an existing app with the same display name and resets its secret.
    Requires 'az login' with rights to create app registrations, and a signed-in identity
    that is an Admin of the target Fabric workspace.
#>
[CmdletBinding()]
param(
    [string]$DisplayName,
    [string]$WorkspaceId,
    [switch]$SkipWorkspaceGrant
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force

$env = Import-DotEnv
Assert-Command az "Install the Azure CLI: https://learn.microsoft.com/cli/azure/"

if (-not $DisplayName) { $DisplayName = if ($env.SPN_DISPLAY_NAME) { $env.SPN_DISPLAY_NAME } else { 'sp-project-iq-fabric-demo' } }
if (-not $WorkspaceId) { $WorkspaceId = $env.FABRIC_WORKSPACE_ID }
if (-not $WorkspaceId -or $WorkspaceId -eq '00000000-0000-0000-0000-000000000000') {
    throw "FABRIC_WORKSPACE_ID is not set in .env. Set it before running setup_spn.ps1."
}

$acct = az account show 2>$null | ConvertFrom-Json
if (-not $acct) { throw "Not logged in. Run 'az login' first." }
$tenantId = $acct.tenantId
Write-Host "Tenant: $tenantId  |  Signed in as: $($acct.user.name)" -ForegroundColor Cyan

Write-Host "== App registration '$DisplayName' ==" -ForegroundColor Cyan
$appId = az ad app list --display-name $DisplayName --query "[0].appId" -o tsv
if (-not $appId) {
    Write-Host "  Creating app registration..."
    $appId = az ad app create --display-name $DisplayName --sign-in-audience AzureADMyOrg --query appId -o tsv
} else { Write-Host "  Reusing existing app (appId=$appId)" }

$spObjectId = az ad sp list --filter "appId eq '$appId'" --query "[0].id" -o tsv
if (-not $spObjectId) {
    Write-Host "  Creating service principal..."
    $spObjectId = az ad sp create --id $appId --query id -o tsv
} else { Write-Host "  Service principal exists (objectId=$spObjectId)" }

Write-Host "== Client secret ==" -ForegroundColor Cyan
$secret = az ad app credential reset --id $appId --display-name 'project-iq-demo' --years 1 --query password -o tsv
if (-not $secret) { throw "Failed to create a client secret for appId=$appId." }
Write-Host "  Secret created (stored in .env; not shown)."

Set-DotEnvValue -Key 'SPN_APP_ID'        -Value $appId
Set-DotEnvValue -Key 'SPN_CLIENT_SECRET' -Value $secret
Set-DotEnvValue -Key 'SPN_TENANT_ID'     -Value $tenantId
Set-DotEnvValue -Key 'SPN_DISPLAY_NAME'  -Value $DisplayName

if ($SkipWorkspaceGrant) {
    Write-Warning "Skipping workspace grant. Add the SPN as workspace Admin manually."
} else {
    Write-Host "== Granting Admin on Fabric workspace $WorkspaceId ==" -ForegroundColor Cyan
    if (-not $spObjectId) { $spObjectId = az ad sp show --id $appId --query id -o tsv 2>$null }
    if (-not $spObjectId) {
        Write-Warning "  Could not resolve the service principal object id; skipping automatic grant."
    } else {
        $userToken = az account get-access-token --resource 'https://api.fabric.microsoft.com' --query accessToken -o tsv
        $body = @{ principal = @{ id = $spObjectId; type = 'ServicePrincipal' }; role = 'Admin' }
        $granted = $false; $lastErr = ''
        for ($attempt = 1; $attempt -le 6 -and -not $granted; $attempt++) {
            try {
                Invoke-FabricApi -Method POST -Path "/workspaces/$WorkspaceId/roleAssignments" `
                    -Body $body -Token $userToken | Out-Null
                $granted = $true
            } catch {
                $lastErr = $_.ErrorDetails.Message; if (-not $lastErr) { $lastErr = $_.Exception.Message }
                if ($lastErr -match '409' -or $lastErr -match 'already' -or $lastErr -match 'PrincipalAlready') {
                    Write-Host "  SPN already has a role on the workspace." -ForegroundColor Green; $granted = $true
                } elseif ($attempt -lt 6) {
                    Write-Host "  Attempt $attempt failed (SP may still be propagating); retrying in 10s..." -ForegroundColor Yellow
                    Start-Sleep -Seconds 10
                }
            }
        }
        if ($granted) { Write-Host "  SPN granted Admin on the workspace." -ForegroundColor Green }
        else {
            Write-Warning "  Could not grant workspace Admin automatically after retries."
            Write-Warning "  Fabric error: $lastErr"
            Write-Host "  Add it manually: Workspace -> Manage access -> Add '$DisplayName' as Admin." -ForegroundColor Yellow
            Write-Host "  (Also enable the tenant setting 'Service principals can use Fabric APIs'.)" -ForegroundColor Yellow
            Write-Host "  Reference: appId=$appId  objectId=$spObjectId" -ForegroundColor DarkGray
        }
    }
}

Write-Host ''
Write-Host 'Service principal ready. Values written to .env:' -ForegroundColor Green
Write-Host "  SPN_APP_ID = $appId"
Write-Host "  SPN_TENANT_ID = $tenantId"
Write-Host 'Next: .\scripts\10_provision_fabric.ps1' -ForegroundColor Green
