<#
.SYNOPSIS
    Deploy the ProjectControlsIQ Direct Lake semantic model (Phase 3) to the Fabric workspace.

.DESCRIPTION
    Reads the TMDL definition folder produced by fabric/semantic-model/build_semantic_model.py,
    base64-encodes every part, and creates (or updates, if it already exists) the semantic model
    in the workspace via the Fabric REST API. Uses the same dual-auth model as the other scripts
    (SPN if .env carries creds, else the signed-in az user). Writes SEMANTIC_MODEL_ID back to .env.

.NOTES
    Requires the Lakehouse silver tables to exist (20_load_data.ps1). Direct Lake reads them live.
#>
[CmdletBinding()]
param(
    [string]$ModelName = 'ProjectControlsIQ',
    [string]$DefinitionRoot
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$env = Import-DotEnv

$ws = $env.FABRIC_WORKSPACE_ID
if (-not $ws) { throw 'FABRIC_WORKSPACE_ID not set in .env.' }
if (-not $DefinitionRoot) {
    $DefinitionRoot = Join-Path (Get-RepoRoot) "fabric\semantic-model\$ModelName.SemanticModel"
}
if (-not (Test-Path $DefinitionRoot)) {
    throw "Definition folder not found: $DefinitionRoot. Run fabric/semantic-model/build_semantic_model.py first."
}

$useSpn = [bool]($env.SPN_APP_ID -and $env.SPN_CLIENT_SECRET -and $env.SPN_TENANT_ID)
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
Write-Host "== Deploying semantic model '$ModelName' ($($parts.Count) parts) ==" -ForegroundColor Cyan

# --- Does a model with this name already exist? ---
$existing = (Invoke-FabricApi -Method GET -Path "/workspaces/$ws/semanticModels" -Token $token).value |
    Where-Object { $_.displayName -eq $ModelName } | Select-Object -First 1

if ($existing) {
    Write-Host "  Updating existing model (id=$($existing.id))"
    $body = @{ definition = @{ parts = $parts } }
    Invoke-FabricLro -Path "/workspaces/$ws/semanticModels/$($existing.id)/updateDefinition" -Body $body -Token $token | Out-Null
    $modelId = $existing.id
}
else {
    Write-Host "  Creating new model"
    $body = @{ displayName = $ModelName; definition = @{ parts = $parts } }
    Invoke-FabricLro -Path "/workspaces/$ws/semanticModels" -Body $body -Token $token | Out-Null
    Start-Sleep -Seconds 3
    $modelId = ((Invoke-FabricApi -Method GET -Path "/workspaces/$ws/semanticModels" -Token $token).value |
        Where-Object { $_.displayName -eq $ModelName } | Select-Object -First 1).id
}

if (-not $modelId) { throw "Deployment reported success but the model could not be found by name." }
Set-DotEnvValue -Key 'SEMANTIC_MODEL_ID' -Value $modelId
Set-DotEnvValue -Key 'SEMANTIC_MODEL_NAME' -Value $ModelName

Write-Host ''
Write-Host "Semantic model deployed. id=$modelId" -ForegroundColor Green
Write-Host "Next: refresh (Direct Lake framing) then validate with DAX:" -ForegroundColor Green
Write-Host "  .\scripts\40_refresh_semantic_model.ps1   (or trigger a refresh in the portal)"
