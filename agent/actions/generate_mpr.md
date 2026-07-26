# Action — Generate Monthly Progress Report (MPR)

The hero action. Produces a project's **Monthly Progress Report** by fusing structured facts (Fabric
Data Agent) with house style + prior-report structure (Azure AI Search). Demo target: **Project
Falcon (PRJ-001)**.

## Trigger
"Generate this month's MPR for **{project}**." / "Write the Monthly Progress Report for {project}."

## Inputs
| Input | Source |
|---|---|
| `project_id` / `project_name` | user (default hero = PRJ-001 Project Falcon) |
| `period` | user or the latest cost period in the model |

## Steps
1. **Resolve the project** — map name → `project_id` via the Data Agent.
2. **Pull structured facts** (Fabric Data Agent), all for this project:
   - `Schedule Risk Score`, `Risk Band`
   - non-SAP: `Schedule Slip (days)`, `Critical Path At Risk`, `Min Total Float (days)`,
     approved ECs w/ `Approved EC Schedule Impact (days)`
   - SAP: `Forecast Overrun`, `Cost To Complete`, `Earned Value`, `Late Long-Lead POs` (+ the
     specific late long-lead PO / material / supplier)
   - the WBS element(s) where a SAP driver and a non-SAP driver land on the **same** work package
3. **Pull narrative grounding** (AI Search):
   - `doc_type = standard` → MPR Authoring Standard (required sections) + escalation policy
   - `doc_type = prior_report`, `project_id = {project_id}` → last month's MPR as the exemplar
4. **Compose** the MPR following the authoring standard's sections (typical):
   1. Executive Summary — overall status + `Risk Band` + the headline
   2. Schedule Status — slip, critical path, float (**non-SAP**)
   3. Cost Status — budget vs forecast, overrun, EV (**SAP**)
   4. Procurement Status — long-lead POs, the late transformer PO (**SAP**)
   5. Key Risks & the **cross-system** finding — the WBS carrying both a late PO and negative
      critical-path float, incl. the driving EC (e.g., EC-1207)
   6. Escalation & Actions — per the policy for a Red project
5. **Ground every number** in step 2; **match structure/tone** to step 3. No invented figures.

## Output
Markdown MPR. For Falcon: Red band (~96), transformer-PO delay + ~$1M overrun (SAP) tied to the same
piping WBS as the +18-day approved EC and negative critical-path float (non-SAP), with escalation.

## Acceptance
- All numbers reconcile with the semantic model / `out/manifest.json`.
- Section set matches the MPR Authoring Standard; reads like the prior Falcon MPR.
- The cross-system paragraph explicitly names one **SAP** and one **non-SAP** driver on a shared WBS.
