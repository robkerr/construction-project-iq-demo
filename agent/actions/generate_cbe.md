# Action — Generate Commercial Bid Evaluation (CBE)

Produces a **Commercial Bid Evaluation** for a tagged-equipment RFQ by fusing structured facts
(Fabric Data Agent) with the commercial-evaluation house standard + prior CBE exemplars (Azure AI
Search). Demo target: **RFQ-0001 — 230 kV main power transformer (tag ET-1001), Project Falcon**.

CBE **depends on the TBE** — only technically qualified bidders are commercially ranked. See
`generate_tbe.md`.

## Trigger
"Generate the **commercial bid evaluation** for **{RFQ / equipment tag}**." /
"Who should we award {equipment} to, and why?" / "Compare the quoted vs evaluated prices for {tag}."

## Inputs
| Input | Source |
|---|---|
| `rfq_id` / `equipment_tag` | user (default hero = RFQ-0001 / ET-1001) |
| `currency` | resolved from the RFQ |

## Steps
1. **Resolve the RFQ** — map equipment tag / description → `rfq_id` via the Data Agent (`dim_rfq`),
   and read the `Engineers Estimate`.
2. **Pull structured facts** (Fabric Data Agent), all scoped to this RFQ, from `fact_bid`:
   - per bidder: `Quoted Price`, `spares_price`, `freight_price`, and the normalized
     **`Evaluated Price`** with its `price_loading` breakdown
   - the commercial terms that drive loadings: `delivery_weeks` / `weeks_late`,
     `payment_advance_pct`, `warranty_months`, `incoterms`, `commercial_deviation_count`
   - the technical gate: `is_technically_qualified` / `tbe_status` (exclude disqualified bidders)
   - `Lowest Quoted Price`, `Lowest Evaluated Price`, `Recommended Evaluated Price`,
     `Recommended Supplier`, and `Evaluated vs Lowest Quote`
   - `cbe_rank` / `award_status` (Recommended / Alternate / Not Recommended / Disqualified)
3. **Pull narrative grounding** (AI Search):
   - `doc_type = standard` → **Commercial Bid Evaluation Standard** (price-normalization method:
     spares, freight, schedule-delay cost, financing of advance payment, warranty/commercial-deviation
     loadings; the lowest-evaluated-qualified award rule)
   - `doc_type = supplier_bid` → the supplier quotations for the commercial terms narrative
   - `doc_type = prior_report` → a prior CBE as the exemplar for section order and tone
4. **Compose** the CBE following the standard's sections (typical):
   1. Purpose & scope — the RFQ, engineer's estimate, qualified-bidder shortlist from the TBE
   2. Evaluation basis — the price-normalization (evaluated-price) methodology
   3. Commercial terms comparison — price, delivery, payment, warranty, Incoterms per bidder
   4. **Evaluated-price bridge** — quoted price → +spares/freight → +schedule/financing/deviation
      loadings → evaluated price, per qualified bidder
   5. Ranking & recommendation — lowest **evaluated** price among qualified bidders wins; name the
      recommended supplier, the alternate, and the evaluated premium over the lowest raw quote
   6. Award note — the headline story: the **cheapest quote is not the best value**
5. **Ground every price/loading** in step 2; **match structure/tone** to step 3. No invented figures.

## Output
Markdown CBE. For RFQ-0001: **Henderson Systems** had the lowest quote (~$3.6M) but is excluded
(technically disqualified); among qualified bidders **Johnson Steel Works** wins on lowest **evaluated**
price (~$4.4M) over **Walker Manufacturing** (~$4.6M) — the recommended award, with the evaluated
premium over the lowest raw quote quantified.

## Acceptance
- Quoted/evaluated prices, loadings, ranks, and the recommended supplier reconcile with the semantic
  model / `out/manifest.json`.
- Section set matches the Commercial Bid Evaluation Standard; reads like the prior CBE.
- Disqualified bidders are excluded from the ranking; the recommendation is the lowest **evaluated**
  qualified bid, not the lowest raw quote — and the report says so explicitly.
