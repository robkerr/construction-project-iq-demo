# Action — Draft Change Notice

Drafts a **change notice** for a schedule/cost-impacting event, using the Change-Notice Template and
the structured facts behind the change. Demo target: the **Project Falcon** long-lead transformer
delay + its approved engineering change (EC-1207).

## Trigger
"Draft a change notice for **{project}** — {issue}." /
"Create a change notice for the Project Falcon transformer delay."

## Inputs
| Input | Source |
|---|---|
| `project_id` / `project_name` | user (default PRJ-001 Project Falcon) |
| `driver` | the EC or PO driving the change (e.g., EC-1207, or the late long-lead PO) |

## Steps
1. **Resolve** the project and the driving record (Data Agent):
   - the approved engineering change — `ec_id`, `title`, `discipline`, `schedule_impact_days`,
     `affected_activity_id`, `wbs_id`
   - and/or the late long-lead PO — `po_id`, `material_desc`, `supplier`, `promised_date` vs
     `revised_date`
2. **Fetch the template** (AI Search) — `doc_type = spec`, title "Change-Notice Template".
3. **Fill the template** with the resolved facts:
   - Project & WBS affected · originating EC/PO · discipline
   - Schedule impact (days) and the affected critical-path activity
   - Cost impact (from `Forecast Overrun` / affected WBS cost) — **SAP**
   - Justification and requested disposition (approve / mitigate)
4. **Ground** all identifiers, dates, and amounts in step 1 — no invented values.

## Output
A completed change notice (markdown) matching the template. For Falcon: the transformer PO slip
(**SAP** procurement) and/or EC-1207 (**non-SAP**, +18 days, Piping, Approved) on the affected WBS,
with the schedule and cost impact quantified.

## Acceptance
- IDs, dates, and impacts match the semantic model (EC-1207 = +18 days, Approved, Piping).
- Format follows the Change-Notice Template exactly.
- Links the SAP procurement delay and the non-SAP schedule impact on the same WBS where applicable.
