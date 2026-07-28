# Action — Generate Technical Bid Evaluation (TBE)

Produces a **Technical Bid Evaluation** for a tagged-equipment RFQ by fusing structured facts (Fabric
Data Agent) with the technical-evaluation house standard + prior TBE exemplars (Azure AI Search).
Demo target: **RFQ-0001 — 230 kV main power transformer (tag ET-1001), Project Falcon**.

## Trigger
"Generate the **technical bid evaluation** for **{RFQ / equipment tag}**." /
"Evaluate the bids for the {equipment} technically." / "Which bidders are technically compliant for {tag}?"

## Inputs
| Input | Source |
|---|---|
| `rfq_id` / `equipment_tag` | user (default hero = RFQ-0001 / ET-1001) |
| `material_category` | resolved from the RFQ (Heat Exchanger / Centrifugal Pump / Electrical Equipment) |

## Steps
1. **Resolve the RFQ** — map equipment tag / description → `rfq_id` and `material_category` via the
   Data Agent (`dim_rfq`).
2. **Pull structured facts** (Fabric Data Agent), all scoped to this RFQ:
   - per bidder: `Avg Technical Score`, `tbe_status`, `is_technically_qualified`,
     `tech_compliant_count` / `tech_deviation_count` / `tech_exception_count`
   - the **compliance matrix** from `fact_bid_tech_eval`: each `requirement` × `supplier`, its
     `required_value` vs `quoted_value`, `compliance` (Compliant / Deviation / Exception), whether
     the requirement `is_mandatory`, and the evaluator `comment`
   - `Qualified Bids` / `Disqualified Bids` counts, and which supplier(s) are **disqualified** and why
     (name the mandatory exception that disqualified them)
3. **Pull narrative grounding** (AI Search):
   - `doc_type = standard` → **Technical Bid Evaluation Standard** (scoring method, weighting,
     compliance definitions, qualification rule) + the datasheet requirements for the category
   - `doc_type = prior_report` → a prior TBE as the exemplar for section order and tone
4. **Compose** the TBE following the standard's sections (typical):
   1. Purpose & scope — the RFQ, equipment tag, category, datasheet reference
   2. Evaluation basis — weighted-scoring method, compliance definitions, qualification threshold
   3. Bidder-by-bidder technical assessment — score, status, notable deviations/exceptions
   4. **Compliance matrix** — requirement × bidder table with Compliant / Deviation / Exception
   5. Technically qualified bidders — the shortlist carried forward to commercial evaluation
   6. Disqualifications — each disqualified bidder + the specific mandatory requirement failed
   7. Recommendation — technically qualified shortlist for the CBE
5. **Ground every score/count** in step 2; **match structure/tone** to step 3. No invented figures.

## Output
Markdown TBE. For RFQ-0001: three of four bidders technically qualify; **Henderson Systems**
(high-risk supplier, the cheapest quote) is **Non-Compliant / disqualified** on a mandatory
requirement (e.g., short-circuit withstand / insulation class), while **Johnson Steel Works**
(score **100**) and **Walker Manufacturing** (score ~**96.6**, compliant with deviations) qualify.

## Acceptance
- Bidder scores, status, and the compliance matrix reconcile with the semantic model / `out/manifest.json`.
- Section set matches the Technical Bid Evaluation Standard; reads like the prior TBE.
- The disqualification paragraph names the **mandatory** requirement each disqualified bidder failed.
- The output feeds the CBE shortlist (only technically qualified bidders proceed).
