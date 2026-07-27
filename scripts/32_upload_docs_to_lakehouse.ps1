<#
.SYNOPSIS
    Publish the unstructured knowledge corpus (Phase 4) to the Lakehouse Files/ section in OneLake.

.DESCRIPTION
    Uploads every document listed in docs/corpus_index.json — plus the catalog itself — to
    Files/<Prefix>/ in the Lakehouse via the OneLake ADLS Gen2 DFS API (Send-OneLakeFile).
    This makes the corpus the canonical, Fabric-resident source of record: the docs are visible in
    the Lakehouse alongside the data, and search/build_index.py reads them straight from OneLake
    (DOCS_SOURCE=onelake) before pushing them into the Azure AI Search index.

    Note: this uses a "push from OneLake" pattern (read the files, push to the index). Azure AI Search
    also has a native OneLake files indexer that can crawl the lakehouse automatically; the demo uses
    push instead for simplicity (no managed-identity/workspace-role setup) and to keep the
    doc_type/project_id facets sourced from corpus_index.json.

.NOTES
    OneLake DFS endpoint https://onelake.dfs.fabric.microsoft.com (x-ms-version 2021-08-06).
    The signed-in identity (or SPN) must be a workspace member with write access to the Lakehouse.
#>
[CmdletBinding()]
param(
    [string]$Prefix = 'knowledge'   # target folder under Files/ (Files/knowledge/...)
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$env = Import-DotEnv

$ws = $env.FABRIC_WORKSPACE_ID
$lh = $env.FABRIC_LAKEHOUSE_ID
if (-not $ws) { throw 'FABRIC_WORKSPACE_ID not set in .env.' }
if (-not $lh) { throw 'FABRIC_LAKEHOUSE_ID not set in .env.' }

$docsRoot = Join-Path (Get-RepoRoot) 'docs'
$catalog = Join-Path $docsRoot 'corpus_index.json'
if (-not (Test-Path $catalog)) {
    throw "docs/corpus_index.json not found. Run data_gen/docs_gen.py first."
}

$entries = Get-Content $catalog -Raw | ConvertFrom-Json
$token = Get-StorageToken

Write-Host "Publishing $($entries.Count) docs + catalog to Files/$Prefix/ in Lakehouse $lh ..." -ForegroundColor Cyan

# The catalog itself, so build_index.py can enumerate the corpus from OneLake.
Send-OneLakeFile -WorkspaceId $ws -LakehouseId $lh `
    -RelativePath "Files/$Prefix/corpus_index.json" -LocalPath $catalog -Token $token
Write-Host "  uploaded corpus_index.json"

foreach ($e in $entries) {
    $local = Join-Path $docsRoot ($e.path -replace '/', '\')
    if (-not (Test-Path $local)) { throw "Missing corpus file: $($e.path). Re-run data_gen/docs_gen.py." }
    Send-OneLakeFile -WorkspaceId $ws -LakehouseId $lh `
        -RelativePath "Files/$Prefix/$($e.path)" -LocalPath $local -Token $token
    Write-Host "  uploaded $($e.path)"
}

Set-DotEnvValue -Key 'DOCS_ONELAKE_PREFIX' -Value "Files/$Prefix"
Set-DotEnvValue -Key 'DOCS_SOURCE' -Value 'onelake'
Write-Host "`nDone. Corpus is in Files/$Prefix/. build_index.py will read from OneLake (DOCS_SOURCE=onelake)." -ForegroundColor Green
