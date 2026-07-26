# Phase 5 — Power BI: "Portfolio Schedule Risk" dashboard

One page that makes the story legible in five seconds: **Project Falcon is the #1 schedule risk,
and it's driven by BOTH a non-SAP schedule slip AND a late SAP long-lead PO + cost overrun.** Built
on the **Project Controls IQ** semantic model (Phase 3) so every visual uses the shared measures.

## Page: *Portfolio Schedule Risk*

### 1. KPI band (top, 4 cards)
| Card | Measure | Note |
|---|---|---|
| Projects At Risk | `Projects At Risk` | count with score ≥ 26 (Amber+Red) |
| Worst Schedule Risk | `MAX` of `Schedule Risk Score` | shows ~96 (Falcon) |
| Total Forecast Overrun | `Total Forecast Overrun` | **SAP** signal — currency |
| Late Long-Lead POs | `Total Late Long-Lead POs` | **SAP** signal — count |

### 2. Risk-ranked bar (hero visual, left/center)
- **Clustered bar**, Y = `dim_project[project_name]`, X = `Schedule Risk Score`, sorted desc.
- Data color by `Risk Band` (Red ≥ 61 / Amber 26–60 / Green < 26).
- **Project Falcon** sits clearly at the top in Red — the "so what" of the page.
- Cross-filters every other visual on click.

### 3. Cross-system driver tiles (right rail — the point of the demo)
Two labeled groups so viewers *see* both systems contributing to the selected project:

- **Non-SAP — Schedule (Primavera / change control)**
  - `Schedule Slip (days)` · `Critical Path At Risk` · `Min Total Float (days)` ·
    `Approved EC Schedule Impact (days)`
- **SAP — Cost & Procurement**
  - `Forecast Overrun` · `Cost To Complete` · `Late Long-Lead POs` · `Earned Value`

Tile subtitles carry the **SAP** / **non-SAP** label explicitly. With Falcon selected, at least one
tile in *each* group is non-zero — the coexistence proof.

### 4. Driver detail table (bottom)
Table at WBS grain for the selected project, columns:
`dim_wbs[wbs_name]`, `dim_wbs[discipline]`, `Critical Path At Risk`, `Min Total Float (days)`,
`Late Long-Lead POs`, `Forecast Overrun`, and an `origin_system` tag column.
This is where a viewer drills into Falcon and finds the **same WBS** carrying both the late SAP
transformer PO and the Primavera critical-path slip.

### 5. Slicers
- `dim_project[region]`, `dim_project[client]`, `Risk Band`, `sap_supplier[risk_rating]`.

## Design notes
- Theme: neutral/corporate (generic — no client branding). Red/Amber/Green only for risk bands.
- Every number traces to a `measures.dax` measure — no visual-level ad-hoc calcs, so the dashboard
  and the agent always agree.
- Add a "Generate MPR for selected project" button (Phase 6) that deep-links / triggers the agent
  action with the selected `project_id`.

## Acceptance
- With no filter, the bar ranks **PRJ-001 Project Falcon #1 (Red, ~96)**.
- Selecting Falcon lights up ≥1 **SAP** tile and ≥1 **non-SAP** tile, and the detail table shows a
  WBS with both a late long-lead PO and negative critical-path float.
- KPI band matches `out/manifest.json` (worst score, projects-at-risk count).
