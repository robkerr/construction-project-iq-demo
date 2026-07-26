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
