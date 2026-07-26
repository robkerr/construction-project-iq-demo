# Phase 3 — Semantic model: "Project Controls IQ"

A single governed model that makes the **schedule-risk vocabulary** queryable by Power BI **and**
by the Fabric Data Agent. The model's reason for existing: expose measures that **fuse SAP cost +
procurement with non-SAP schedule** so one number (`Schedule Risk Score`) ranks the portfolio.

Build it as a **Direct Lake** model over the Lakehouse `silver` tables (detail grain lets the agent
slice by project, discipline, supplier, period). `gold.project_schedule_risk` remains the
pre-aggregated fast path / validation table.

## Tables (import from `silver`)

| Table | Grain | Origin | Role |
|---|---|---|---|
| `dim_project` | 1 row / project | non-SAP | dimension (hero = PRJ-001 Project Falcon) |
| `dim_wbs` | 1 row / WBS element | non-SAP | **bridge** — the SAP ↔ non-SAP join key |
| `fact_schedule_activity` | 1 row / activity | non-SAP (Primavera) | schedule facts |
| `fact_engineering_change` | 1 row / EC | non-SAP | change-control facts |
| `sap_fi_cost` | 1 row / WBS / period | **SAP** FI | cost facts |
| `sap_mm_po` | 1 row / PO | **SAP** MM | procurement facts |
| `sap_supplier` | 1 row / supplier | **SAP** | supplier dimension |

## Relationships

```
dim_project (project_id) 1───* dim_wbs (project_id)

dim_wbs (wbs_id) 1───* fact_schedule_activity (wbs_id)     [non-SAP]
dim_wbs (wbs_id) 1───* fact_engineering_change (wbs_id)    [non-SAP]
dim_wbs (wbs_id) 1───* sap_fi_cost (wbs_id)                [SAP]      ◄── the load-bearing
dim_wbs (wbs_id) 1───* sap_mm_po (wbs_id)                  [SAP]      ◄── cross-system join

sap_supplier (supplier_id) 1───* sap_mm_po (supplier_id)   [SAP]
```

`dim_wbs` is the **bridge**: because SAP cost/PO rows and non-SAP schedule/EC rows both carry
`wbs_id` (+ `project_id`), the model can attribute a late **SAP** transformer PO and a **non-SAP**
Primavera critical-path slip to the *same* WBS element on the *same* project. That co-attribution is
the demo.

- All single-direction (`dim → fact`), single (`1:*`) relationships.
- `dim_project[project_id]` is the model's default cross-filter axis for portfolio views.

## Measures

Author the measures from [`../measures.dax`](../measures.dax) verbatim. They reproduce the exact
formula used by `data_gen/generate.py::rank_projects`, so the model's ranking matches the generator:

`Schedule Risk Score = min(100, slip*1.5 + neg_float*2 + cp_at_risk*3 + late_long_lead_pos*5 + overrun/100000)`

Key measures: **Schedule Slip (days)**, **Critical Path At Risk**, **Min Total Float (days)**,
**Approved EC Schedule Impact (days)** (non-SAP); **Forecast Overrun**, **Cost To Complete**,
**Earned Value** (SAP FI); **Late Long-Lead POs** (SAP MM); and the fused **Schedule Risk Score**
+ **Risk Band**.

## Prep for AI / Copilot (Data Agent grounding)
- **Verified answer:** "Which project has the highest schedule risk?" → returns Project Falcon
  (PRJ-001) with its drivers. Pin as a verified answer so the agent is deterministic.
- **Custom instructions:** always report the score *with its drivers*, and label each driver
  **SAP** (cost/procurement) or **non-SAP** (schedule/change) so the coexistence story is explicit.
- **Synonyms:** "at risk" → high `Schedule Risk Score`; "float"/"slack" → `total_float_days`;
  "long-lead" → `is_long_lead`; "overrun" → `Forecast Overrun`.
- Mark `project_name`, `wbs_name`, `discipline`, `supplier_name` as the descriptive columns the
  agent may surface; hide raw surrogate keys from Q&A.

## Acceptance
- `Schedule Risk Score` by `project_id` ranks **PRJ-001 (Falcon) #1**, matching `out/manifest.json`.
- For Falcon, `Late Long-Lead POs > 0` (SAP) **and** `Critical Path At Risk > 0` (non-SAP) — both
  driver families fire, proving the cross-system fusion.
- The same measures resolve identically whether sliced in Power BI or asked of the Data Agent.
