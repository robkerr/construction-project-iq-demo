# Project Controls IQ — "Art of the Possible" Demo

A self-contained, **100% synthetic** demo showing how Microsoft Fabric + Azure AI Foundry + M365
Copilot turn siloed **SAP** (cost, procurement) and **non-SAP** (schedule, engineering change) data
into one governed answer: **which project is most at risk, why, and here's the Monthly Progress
Report.**

> **Generic branding.** The fictional EPC contractor is **Contoso Engineering & Construction**.
> Clients (Northwind Energy, Fabrikam, Adventure Works, …) and projects (Falcon, Kestrel, Osprey, …)
> are fictional. **No customer-specific data or names appear anywhere** — safe to show to anyone.

## The story
Twelve capital projects. One — **Project Falcon (PRJ-001)** — is the clear #1 schedule risk, and the
reason spans **both** systems on the **same** work package:
- **SAP** — a late long-lead **main power transformer** PO (PO-00512) and a ~$1M forecast overrun.
- **non-SAP** — an approved engineering change (**EC-1207**, +18 days, Piping) and negative
  critical-path float.

Neither system alone tells you Falcon is in trouble. Fused, it's obvious — and the agent writes the
MPR that says so.

## Architecture / phases
| Phase | Folder | What |
|---|---|---|
| 1. Synthetic data | `data_gen/` | SAP + non-SAP tables (seed 42), deterministic at-risk injection, docs corpus |
| 2. Unify in OneLake | `fabric/` | PowerShell provisioning + medallion notebooks → Lakehouse `gold.project_schedule_risk` |
| 3. Semantic model | `fabric/measures.dax`, `fabric/semantic-model/` | shared measures incl. fused **Schedule Risk Score** |
| 4. Knowledge index | `search/`, `docs/` | Azure AI Search over standards, policies, prior MPRs |
| 5. Dashboard | `powerbi/` | "Portfolio Schedule Risk" page spec |
| 6. Agent | `agent/` | Foundry + M365 Copilot assistant: generate MPR, draft change notice |

## Quick start
```powershell
# 1. Python env + generate data and docs (no cloud needed — verify the story locally)
py -3.12 -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r data_gen/requirements.txt
python data_gen/generate.py     # writes out/parquet, out/csv, out/manifest.json — prints the ranking
python data_gen/docs_gen.py     # writes docs/ (corpus for Phase 4)

# 2. author the Fabric notebooks
python fabric/notebooks/build_notebooks.py

# 3. cloud: copy .env.example -> .env, fill it in, then provision + load
#    az login;  ./scripts/setup_spn.ps1;  ./scripts/10_provision_fabric.ps1;  ./scripts/20_load_data.ps1
```
See [`fabric/load_to_lakehouse.md`](fabric/load_to_lakehouse.md) for the full cloud run order.

## What you get locally (no Azure required)
Running Phase 1 alone proves the demo: `generate.py` prints the portfolio ranking with **Project
Falcon #1 (~96, Red)**, its drivers spanning SAP + non-SAP, and writes a reproducible dataset
(`out/manifest.json`). `docs_gen.py` writes prior Falcon MPRs whose numbers match the data.

## Deployment guide (repeatable)

This is the full, ordered playbook for landing the demo in a Fabric workspace. It marks each step
**🤖 automated** (a script does it) or **🧑 manual** (you do it in a portal). Phases 2, 3, and 5 are
fully scripted (data load, Direct Lake semantic model, and the Power BI report); Phase 4 needs a
one-time Search provisioning, and Phase 6 (agents) is portal work Fabric/Foundry don't yet expose as
stable public APIs.

### Prerequisites (🧑 manual, once)
1. A Fabric workspace on an **F2+ or Trial capacity**. Copy its ID from the URL
   (`.../groups/<WORKSPACE_ID>/list`).
2. Tools: **PowerShell 7+**, **Azure CLI** (`az`), **Python 3.12**. Run `./scripts/00_prereqs.ps1`
   to check.
3. `py -3.12 -m venv .venv` and `pip install -r data_gen/requirements.txt`.
4. Generate data + notebooks locally (proves the story before any cloud):
   ```powershell
   ./.venv/Scripts/python.exe data_gen/generate.py          # writes out/*.parquet + manifest
   ./.venv/Scripts/python.exe data_gen/docs_gen.py           # writes docs/ corpus (Phase 4)
   ./.venv/Scripts/python.exe fabric/notebooks/build_notebooks.py   # authors the 3 medallion notebooks
   ```
5. `cp .env.example .env` and set at minimum `FABRIC_WORKSPACE_ID`. Leave `FABRIC_LAKEHOUSE_ID`
   blank — the provision script fills it in.

### Choose an auth mode
The Phase 2 scripts work **two** ways and auto-detect which to use:

| Mode | When | How |
|---|---|---|
| **Signed-in user** (delegated) | quick, interactive runs | `az login` as a workspace **Member/Admin**. Leave `SPN_*` blank in `.env`. Scripts fall back to your `az` token. |
| **Service principal** (SPN) | repeatable / CI / unattended | 🤖 `./scripts/setup_spn.ps1` creates the SPN, grants it workspace **Admin**, writes `SPN_*` to `.env`. Requires the tenant setting **"Service principals can use Fabric APIs"** (Fabric admin portal). |

The scripts print `Auth: signed-in Azure CLI user` or `Auth: service principal (...)` at the top of
each run so you can confirm which path is active.

### Phase 2 — Provision + load OneLake (🤖 automated)
```powershell
az login                                    # or run setup_spn.ps1 for the SPN path
./scripts/10_provision_fabric.ps1           # creates schema-enabled Lakehouse, uploads 8 parquet, imports notebooks
./scripts/20_load_data.ps1                  # runs 01→02→03 via the RunNotebook API; builds bronze/silver/gold
```
- `10_provision_fabric.ps1` creates Lakehouse `lh_project_intelligence` (schemas enabled), writes
  `FABRIC_LAKEHOUSE_ID` back to `.env`, uploads `out/*.parquet` to `Files/landing/`, and imports the
  three notebooks. Re-run with **`-SkipUpload`** to re-import notebook edits without re-uploading data.
- `20_load_data.ps1` runs the medallion notebooks in order and polls each to completion (Spark cold
  start ≈ 1–2 min per notebook). Use **`-Only 03_build_silver_gold`** to re-run a single stage.
- **Verify:** `gold.project_schedule_risk` must rank **Project Falcon (PRJ-001) #1** (score ≈ 96,
  Red) with **both** a SAP driver (late long-lead PO / overrun) and a non-SAP driver
  (slip / critical-path). Confirmed row counts on a good run: 12 projects, 11 at-risk activities,
  135 late procurement rows.

### Phase 3 — Semantic model (🤖 automated)
A Direct Lake model over the `silver` tables, deployed via the Fabric REST API. Spec:
[`fabric/semantic-model/README.md`](fabric/semantic-model/README.md).

```powershell
./.venv/Scripts/python.exe fabric/semantic-model/build_semantic_model.py   # generates TMDL from .env IDs
./scripts/30_deploy_semantic_model.ps1 -Auth user                          # create/update model, writes SEMANTIC_MODEL_ID
./scripts/40_refresh_semantic_model.ps1                                     # frame Direct Lake so it's queryable
```

- `build_semantic_model.py` emits `ProjectControlsIQ.SemanticModel/` (TMDL): 7 tables mapped 1:1 to
  `silver`, the 6 `dim → fact` relationships (`dim_wbs` is the SAP↔non-SAP bridge), and every measure
  from [`fabric/measures.dax`](fabric/measures.dax) ported verbatim.
- `30_deploy_semantic_model.ps1` base64-encodes the parts and creates/updates the model. **Use
  `-Auth user`** — the model is owned by the signed-in author, so SPN `updateDefinition` returns
  `Unauthorized`. (`-Auth auto|user|spn`.)
- `40_refresh_semantic_model.ps1` runs a Power BI enhanced refresh so the Direct Lake partitions are
  framed — required before the first DAX query. Re-run it after reloading the silver tables.
- Validate with DAX (`executeQueries`): Falcon ranks **#1 at 95.7 (Red)**, matching the gold table.
- 🧑 Optional AI-readiness (verified answer, custom instructions, synonyms per the spec README) is a
  portal step, needed only for the Phase 6 Data Agent.

### Phase 4 — Azure AI Search knowledge index (🤖 script + 🧑 provisioning)
Follow [`search/build_index.md`](search/build_index.md). The corpus's canonical home is the **Lakehouse
`Files/knowledge/` section** (OneLake); `build_index.py` reads it from OneLake and **pushes** each doc
into the index via `SearchClient.upload_documents()` — no separate Azure Storage account needed.
> Azure AI Search *does* have a native [OneLake files indexer](https://learn.microsoft.com/azure/search/search-how-to-index-onelake-files)
> that could crawl the lakehouse automatically (Markdown is supported). We use push for this demo
> because it's simpler for 6 docs — no Search managed identity + Contributor role on the Fabric
> workspace, and it keeps the `doc_type`/`project_id` facets from `corpus_index.json`. Prefer the
> OneLake indexer for a production "auto-index on file drop" pattern.
1. 🧑 Provision an **Azure AI Search** service; set `AI_SEARCH_ENDPOINT` in `.env`. For RBAC auth
   (recommended), enable **Role-based access control** on the service and grant your identity both
   **Search Service Contributor** (create the index) and **Search Index Data Contributor** (upload docs).
   Alternatively, set `AI_SEARCH_ADMIN_KEY` in `.env` to use a key instead.
2. 🤖 Ensure the corpus exists (`./.venv/Scripts/python.exe data_gen/docs_gen.py` regenerates the 6 docs
   from `out/`), publish it to the Lakehouse, then build the index:
   ```powershell
   ./.venv/Scripts/python.exe -m pip install azure-search-documents azure-identity python-dotenv
   pwsh -File ./scripts/32_upload_docs_to_lakehouse.ps1   # -> Files/knowledge/ ; sets DOCS_SOURCE=onelake
   ./.venv/Scripts/python.exe search/build_index.py       # reads OneLake, (re)creates index, uploads 6 docs
   ```
   `build_index.py` reads from OneLake when `DOCS_SOURCE=onelake` (default once workspace+lakehouse are
   set); use `DOCS_SOURCE=local` to index straight from `docs/` offline. With no `AI_SEARCH_ADMIN_KEY`,
   it uses `DefaultAzureCredential` (your `az login`). If it reports
   `AzureCliCredential: Failed to invoke the Azure CLI`, that's a transient cold-start — just re-run once
   (confirm `az account show` works first). Vector search is optional (`AZURE_OPENAI_EMBED_DEPLOYMENT`).
3. ✅ Verify: the run prints `reading corpus from OneLake ...` then `uploaded 6/6 documents`; a
   `search("Falcon schedule risk")` returns the schedule-risk policy and both prior Falcon MPRs.

### Phase 5 — Power BI dashboard (🤖 automated scaffold + 🧑 polish)
A single-page "Portfolio Schedule Risk" report (PBIR) bound `byConnection` to the Phase 3 model.
Spec: [`powerbi/schedule_risk_dashboard.md`](powerbi/schedule_risk_dashboard.md).

```powershell
./.venv/Scripts/python.exe powerbi/build_report.py     # generates ProjectControlsIQ.Report from SEMANTIC_MODEL_ID
./scripts/31_deploy_report.ps1 -Auth user              # create/update report, writes REPORT_ID
# open: https://app.fabric.microsoft.com/groups/<FABRIC_WORKSPACE_ID>/reports/<REPORT_ID>
```

- `build_report.py` lays out the KPI band (4 cards), the hero risk-ranked bar, 8 cross-system driver
  tiles (4 non-SAP schedule · 4 SAP cost/procurement), the WBS detail table, and 4 slicers — every
  binding maps to a real model measure/column.
- Report/visual authoring is **not** exposed by the Fabric modeling tooling, so this is a best-effort,
  API-deployable scaffold. 🧑 Polish in the service: (1) color the hero bar by risk band, and (2) add a
  **Risk Band** slicer — `Risk Band` is a *measure*, so a slicer needs a Risk Band **column** (a
  calculated column can disable Direct Lake; prefer a report-side approach or a bin).

### Phase 6 — Agents (🧑 manual, Fabric + Foundry + M365)
1. **Fabric Data Agent** over the `ProjectControlsIQ` model; grab its **MCP endpoint**
   (`DATA_AGENT_MCP_ENDPOINT`, ends in `/agent`). Ground it with [`agent/grounding.md`](agent/grounding.md)
   and [`agent/system_prompt.md`](agent/system_prompt.md).
2. **Azure AI Foundry agent** (`gpt-4.1`) wiring the Data Agent + AI Search tools, with the two
   actions in [`agent/actions/`](agent/actions/).
3. **M365 Copilot** declarative agent per [`agent/m365_copilot.md`](agent/m365_copilot.md).

### Troubleshooting notes (lessons from this build)
- **Schema-enabled Lakehouse + CTAS + TEMP VIEW = `TABLE_OR_VIEW_NOT_FOUND`.** A
  `CREATE TABLE … AS SELECT` that references a `CREATE OR REPLACE TEMP VIEW` can fail to resolve the
  view's underlying `silver.*` tables. **Fix (already applied in `build_notebooks.py`):** inline the
  aggregations as **CTEs that read `silver.*` directly** inside the single CTAS. Direct `silver.*`
  references inside a CTAS resolve fine.
- **Avoid Delta self-reference.** `CREATE OR REPLACE TABLE x AS SELECT * FROM x` is invalid — fold
  follow-on columns (e.g. `risk_band`) into the same CTAS via a CTE.
- **`.../lakehouses/{id}/tables` returns `UnsupportedOperationForSchemasEnabledLakehouse`** — you
  can't list tables that way on a schema-enabled Lakehouse; query the SQL endpoint instead.
- **Getting the real Spark error:** the RunNotebook job API only returns a generic "session cancelled"
  message. To capture the actual exception, run a diagnostic notebook that wraps each `spark.sql` in
  `try/except`, writes a log to `Files/…txt`, then download it via OneLake DFS
  (`https://onelake.dfs.fabric.microsoft.com/{ws}/{lh}/Files/…` with a storage token +
  header `x-ms-version: 2021-08-06`).
- **`defaultLakehouse` placement:** in the RunNotebook body it must be nested under
  `executionData.configuration` (not directly under `executionData`) or relative `Files/` paths won't
  resolve.

## Repo layout
```
data_gen/     synthetic data + docs generators (seed 42, reproducible)
fabric/       Common.psm1 + PS scripts, notebooks, measures.dax, semantic-model spec, load doc
search/       AI Search index spec + build_index.py
docs/         generated unstructured corpus (committed for review; regen with docs_gen.py)
powerbi/      dashboard spec
agent/        grounding, system prompt, M365 surface, action specs
out/          generated parquet/csv/manifest (git-ignored)
.env.example  all keys (Fabric, SPN, AI Search, Foundry, M365) — generic names
```

## Ground rules
- **Synthetic only.** Deterministic (seed 42) so every run reproduces the same ranking.
- **Generic.** No real company, project, or customer data — reusable for any audience.
- **Proven patterns.** Fabric REST API versions / provisioning patterns reuse what worked in prior
  builds (see `scripts/lib/Common.psm1`).
