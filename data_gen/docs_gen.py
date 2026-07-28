"""Synthetic UNSTRUCTURED corpus generator for the Azure AI Search index.

Writes the "Ask-KOL"-style knowledge the agent grounds its narrative on:
  - standards/   authoring standard + schedule-risk policy
  - specs/       change-notice template + Falcon scope
  - prior_reports/  a few prior monthly progress reports (narrative style the agent emulates)

Numbers used in the prior Falcon MPRs are pulled from the generated data + manifest so the
structured facts and the unstructured language stay consistent. 100% synthetic (Contoso E&C).

Usage:
    python docs_gen.py                 # reads ../out, writes ../docs
    python docs_gen.py --out ../out --docs ../docs
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "out"
DEFAULT_DOCS = HERE.parent / "docs"

COMPANY = "Contoso Engineering & Construction"
COMPANY_SHORT = "Contoso E&C"


def _load(out_dir: Path):
    pq = out_dir / "parquet"
    csv = out_dir / "csv"
    src = pq if pq.exists() else csv
    reader = pd.read_parquet if src == pq else pd.read_csv
    ext = "parquet" if src == pq else "csv"
    frames = {}
    for name in ["dim_project", "sap_mm_po", "sap_supplier", "fact_engineering_change",
                 "sap_fi_cost", "fact_schedule_activity", "dim_rfq", "fact_bid",
                 "fact_bid_tech_eval", "dim_tech_requirement"]:
        frames[name] = reader(src / f"{name}.{ext}")
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    return frames, manifest


def _falcon_facts(frames, manifest):
    """Extract the Falcon numbers so prior MPRs quote the same figures the model would."""
    inj = next(i for i in manifest["injected_projects"] if i["project_id"] == "PRJ-001")
    proj = frames["dim_project"]
    prow = proj[proj["project_id"] == "PRJ-001"].iloc[0]
    ec = frames["fact_engineering_change"]
    ec_row = ec[ec["ec_id"] == inj["ec_id"]].iloc[0]
    po = frames["sap_mm_po"]
    po_row = po[po["po_id"] == inj["po_id"]].iloc[0]
    sup = frames["sap_supplier"]
    sup_row = sup[sup["supplier_id"] == po_row["supplier_id"]].iloc[0]
    cost = frames["sap_fi_cost"]
    overrun = float((cost["forecast_cost"] - cost["budget"])[cost["project_id"] == "PRJ-001"].sum())
    return {
        "project_name": prow["project_name"],
        "client": prow["client"],
        "region": prow["region"],
        "contract_type": prow["contract_type"],
        "pct_complete": float(prow["pct_complete"]),
        "planned_finish": str(prow["planned_finish"]),
        "forecast_finish": str(prow["forecast_finish"]),
        "ec_id": ec_row["ec_id"],
        "ec_impact": int(ec_row["schedule_impact_days"]),
        "ec_discipline": ec_row["discipline"],
        "po_id": po_row["po_id"],
        "po_material": po_row["material_desc"],
        "po_late_days": (pd.to_datetime(po_row["revised_date"]) - pd.to_datetime(po_row["promised_date"])).days,
        "supplier_name": sup_row["supplier_name"],
        "supplier_country": sup_row["country"],
        "min_float": int(inj["min_float"]),
        "worst_slip": int(inj["worst_slip_days"]),
        "overrun": overrun,
    }


def _bid_facts(frames, manifest):
    """Pull the hero RFQ-0001 bid-evaluation numbers + per-bidder technical deviations so the
    TBE/CBE docs quote the same figures the model would."""
    hero = manifest["hero_bid_eval"]
    rfq = frames["dim_rfq"]
    rfq_row = rfq[rfq["rfq_id"] == hero["rfq_id"]].iloc[0]
    reqs = frames["dim_tech_requirement"]
    cat_reqs = reqs[reqs["material_category"] == hero["material_category"]].reset_index(drop=True)
    tev = frames["fact_bid_tech_eval"]
    bid = frames["fact_bid"]
    proj = frames["dim_project"]
    prow = proj[proj["project_id"] == hero["project_id"]].iloc[0]

    bidders = []
    for b in hero["bids"]:
        sid = b["supplier_id"]
        bid_row = bid[(bid["rfq_id"] == hero["rfq_id"]) & (bid["supplier_id"] == sid)].iloc[0]
        devs = tev[(tev["rfq_id"] == hero["rfq_id"]) & (tev["supplier_id"] == sid)
                   & (tev["compliance"] != "Compliant")]
        deviations = [{"requirement": r["requirement"], "required_value": r["required_value"],
                       "compliance": r["compliance"], "mandatory": bool(r["is_mandatory"])}
                      for _, r in devs.iterrows()]
        bidders.append({**b, "bid_id": str(bid_row["bid_id"]), "deviations": deviations,
                        "spares_price": float(bid_row["spares_price"]),
                        "freight_price": float(bid_row["freight_price"]),
                        "price_loading": float(bid_row["price_loading"])})
    return {
        "rfq": hero,
        "project_name": prow["project_name"],
        "client": prow["client"],
        "requirements": [{"requirement": r["requirement"], "required_value": r["required_value"],
                          "unit": r["unit"], "mandatory": bool(r["is_mandatory"]),
                          "weight": int(r["weight"])} for _, r in cat_reqs.iterrows()],
        "bidders": bidders,
    }


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8")
    print(f"  wrote {path.relative_to(path.parents[1])}")


# --------------------------------------------------------------------------- standards
def doc_authoring_standard() -> str:
    return f"""
# Monthly Progress Report (MPR) Authoring Standard
**Owner:** {COMPANY_SHORT} Project Controls Center of Excellence · **Doc type:** standard

Every monthly progress report follows the same structure so that any project's report reads
consistently and can be assembled from the project-controls data of record.

## Required sections
1. **Executive Summary** — 3-5 sentences: overall health (Red/Amber/Green), the single most
   important driver this period, and the recommended action.
2. **Project Management** — scope, milestones, percent complete vs plan, forecast finish vs
   planned finish, and any change-control activity (engineering changes and their schedule impact).
3. **Project Controls** — schedule status (critical-path float, forecast slip in days),
   cost status (budget, forecast, forecast overrun, cost-to-complete exposure, earned value),
   and the top risks with owners.
4. **Supply Chain** — long-lead equipment status, late or at-risk purchase orders, supplier
   performance and any supplier-risk flags.
5. **Look-ahead & Actions** — the 60-day look-ahead and the committed mitigation actions.

## Tone & rules
- Factual and concise. Every number must trace to the project-controls data of record.
- Always state the RAG (Red/Amber/Green) status and justify it with the driving metric.
- Name the specific engineering change (EC id) and purchase order (PO id) when they drive risk.
- Never invent figures; if a number is unavailable, state "not available this period".
- Fuse schedule (Primavera), cost and procurement (SAP) into ONE narrative — do not silo them.
"""


def doc_schedule_risk_policy() -> str:
    return f"""
# Schedule-Risk Classification & Escalation Policy
**Owner:** {COMPANY_SHORT} Project Controls · **Doc type:** standard

{COMPANY_SHORT} classifies project schedule risk using a blended signal that combines NON-SAP
schedule data (Primavera P6) with SAP cost and procurement data. A single governed foundation
is required because no individual system sees the whole picture.

## Risk bands (Schedule Risk Score, 0-100)
- **Green (0-25):** on or ahead of baseline; positive critical-path float; no late long-lead POs.
- **Amber (26-60):** forecast slip present; tightening or slightly negative float; a late
  long-lead PO or a modest forecast overrun.
- **Red (61-100):** material forecast slip; negative critical-path float; a late long-lead PO
  from a High-risk supplier; and/or significant forecast overrun.

## Contributing signals (all must be considered)
| Signal | Source | System |
|---|---|---|
| Forecast slip (days past baseline finish) | Primavera schedule | non-SAP |
| Minimum total float (negative = behind on critical path) | Primavera schedule | non-SAP |
| Critical-path activities forecast to slip | Primavera schedule | non-SAP |
| Approved engineering changes with schedule impact | Engineering-change log | non-SAP |
| Late long-lead purchase orders | SAP Materials Management | SAP |
| Forecast overrun & cost-to-complete exposure | SAP Finance | SAP |
| Supplier risk rating / external disruption signal | SAP vendor master / external | SAP/ext |

## Escalation
- **Red** projects are escalated to the Project Director within 48 hours with a mitigation plan.
- Any **approved** engineering change adding >= 10 days to a critical-path activity triggers an
  immediate change-notice and a schedule re-forecast.
- A late long-lead PO from a **High-risk** supplier requires a supplier recovery plan.
"""


def doc_change_notice_template() -> str:
    return f"""
# Change-Notice Template
**Owner:** {COMPANY_SHORT} Project Controls · **Doc type:** spec

Use this format when drafting a change-notice for a schedule- or cost-impacting event.

```
CHANGE NOTICE
Project:            <project name> (<project_id>)
Raised by:          <role>            Date: <yyyy-mm-dd>
Trigger:            <EC id / PO id / activity id>
Discipline / WBS:   <discipline> / <wbs_id>

Description:
  <what changed and why, 2-4 sentences>

Schedule impact:    <+N days>  on critical-path activity <activity_id>
Cost impact:        <$ forecast overrun / cost-to-complete exposure>
Supply-chain impact:<late long-lead PO <po_id> from <supplier>, revised +N days>

Recommended action: <mitigation>  Owner: <name>  Need-by: <yyyy-mm-dd>
Approval:           <name / status>
```

Rules: cite the driving EC and PO ids; quote schedule impact in days and cost impact in dollars;
always name the affected critical-path activity.
"""


def doc_falcon_scope(f) -> str:
    return f"""
# {f['project_name']} — Project Scope Summary
**Client:** {f['client']} · **Region:** {f['region']} · **Contract:** {f['contract_type']}
**Doc type:** spec · **Project id:** PRJ-001

{f['project_name']} is a {f['contract_type']} engineering, procurement and construction project
delivered by {COMPANY} for {f['client']}. The project is currently in the execution phase
(~{int(round(f['pct_complete']*100))}% complete) with a planned finish of {f['planned_finish']}.

## Scope highlights
- Process, mechanical, piping and electrical/I&C scope across the main process units and offsites.
- Long-lead engineered equipment on the critical path, including a {f['po_material'].lower()}.
- Interface-heavy execution with the client's owner's-engineer change-control process.

## Known critical-path sensitivities
- Engineered long-lead equipment deliveries drive mechanical completion and pre-commissioning.
- Engineering changes on the {f['ec_discipline']} critical path can cascade to system turnover.
"""


def _mpr(period_label: str, f, health: str, slip: int, float_days: int, overrun: float,
         narrative_extra: str) -> str:
    pct = int(round(f["pct_complete"] * 100))
    return f"""
# {f['project_name']} — Monthly Progress Report — {period_label}
**Project:** {f['project_name']} (PRJ-001) · **Client:** {f['client']} · **Prepared by:** {COMPANY_SHORT} Project Controls
**Doc type:** prior_report · **Status:** {health}

## Executive Summary
{f['project_name']} is **{health}** this period. {narrative_extra} The project is approximately
{pct}% complete against a planned finish of {f['planned_finish']}.

## Project Management
- Percent complete: ~{pct}%. Milestone delivery is being managed against the current forecast.
- Change control: engineering changes are tracked in the change log; those with critical-path
  impact are re-forecast into the schedule.

## Project Controls
- Schedule: current forecast slip of about **{slip} day(s)** past baseline finish; minimum
  critical-path total float is **{float_days} day(s)**.
- Cost: forecast overrun of approximately **${overrun:,.0f}** with a corresponding
  cost-to-complete exposure being monitored; earned value is tracked against actuals.

## Supply Chain
- Long-lead equipment is monitored weekly. Purchase order **{f['po_id']}**
  ({f['po_material'].lower()}) from **{f['supplier_name']}** ({f['supplier_country']}) is the
  key delivery to watch.

## Look-ahead & Actions
- 60-day look-ahead focuses on protecting the critical path and recovering long-lead float.
"""


def doc_prior_mpr_recent(f) -> str:
    narrative = (f"The dominant driver is an approved engineering change (**{f['ec_id']}**, "
                 f"+{f['ec_impact']} days) on the {f['ec_discipline']} critical path, compounded by "
                 f"a late long-lead delivery ({f['po_id']}) from a High-risk supplier.")
    return _mpr("June 2026", f, "Amber/Red", max(f["worst_slip"] - 6, 8),
                f["min_float"] + 4, f["overrun"] * 0.7, narrative)


def doc_prior_mpr_older(f) -> str:
    narrative = ("Schedule and cost were broadly on plan, with early warning signs emerging on "
                 "long-lead equipment deliveries that are being monitored.")
    return _mpr("May 2026", f, "Green/Amber", 5, 3, f["overrun"] * 0.2, narrative)


# --------------------------------------------------------------------------- bid evaluation
def doc_tbe_standard() -> str:
    return f"""
# Technical Bid Evaluation (TBE) Standard
**Owner:** {COMPANY_SHORT} Engineering & Procurement · **Doc type:** standard

A Technical Bid Evaluation compares each supplier's technical proposal against the project
**technical datasheet (RFQ requirements)** for a tagged equipment item and determines which bids
are technically acceptable *before* any commercial comparison. The pilot covers three material
categories — **Heat Exchanger**, **Centrifugal Pump**, and **Electrical Equipment** — and is
designed so new categories can be added with minimal configuration (a new requirement set only).

## Compliance categories (per requirement)
- **Compliant** — the offer meets the specified requirement. Scoring factor **1.0**.
- **Deviation** — the offer differs but may be acceptable after normalization. Scoring factor **0.6**;
  every deviation is carried into the Commercial Bid Evaluation as a price loading.
- **Exception** — the requirement is not met or not addressed. Scoring factor **0.0**.

## Technical score
`Technical Score (0-100) = 100 x SUM(weight x factor) / SUM(weight)` across all requirements, where
`weight` reflects the engineering importance of the requirement (mandatory requirements carry the
highest weights).

## Qualification (the gate to commercial evaluation)
A bid is **technically qualified** only if BOTH hold:
1. **No mandatory requirement is an Exception.** Any Exception on a *mandatory* requirement (e.g. a
   missing design-code compliance or type-test certificate) makes the bid **Non-Compliant** and it is
   **disqualified regardless of price**.
2. **Technical Score ≥ 70.**

TBE status resolves to: **Compliant** (no deviations), **Compliant with Deviations** (qualified, one
or more deviations to normalize), or **Non-Compliant** (disqualified).

## Rules
- Never advance a Non-Compliant bid to commercial comparison on the basis of a low price.
- Name the specific unmet requirement (and whether it was mandatory) when disqualifying a bid.
- Every requirement must be evaluated for every bidder; "not addressed" counts as an Exception.
"""


def doc_cbe_standard() -> str:
    return f"""
# Commercial Bid Evaluation (CBE) Standard
**Owner:** {COMPANY_SHORT} Procurement / Supply Chain · **Doc type:** standard

A Commercial Bid Evaluation compares the **technically-qualified** bids on a like-for-like basis and
recommends the **lowest evaluated cost**, not simply the lowest quoted price. It works from the
commercial terms & pricing extracted from each supplier's bid document for the tagged equipment.

## Evaluated price (normalization)
```
Evaluated Price = Quoted Price
               + Recommended Spares
               + Freight
               + Technical-deviation loading      (each carried-forward TBE deviation)
               + Commercial-terms deviation loading (deviations to the standard T&Cs)
               + Schedule loading                  (each week delivery lands past Required-On-Site)
               + Advance-payment financing cost    (cost of any advance payment above the 10% norm)
               + Short-warranty loading            (warranty shorter than the 18-month standard)
```

The loadings put every bid on the same commercial footing: a cheap quote with technical deviations,
a long delivery, a large advance payment, or a short warranty is normalized to what it would truly
cost the project.

## Recommendation
- Rank technically-qualified bids by **Evaluated Price**, ascending.
- **Rank 1 → Recommended award.** **Rank 2 → Alternate.** Remaining qualified bids → Not Recommended.
- Disqualified (Non-Compliant) bids are **excluded from the ranking** even if their quoted price is
  the lowest received.

## Rules
- Always report BOTH the lowest *quoted* price and the recommended *evaluated* price, and explain the
  gap (deviations, schedule, terms).
- Cite the delivery week vs Required-On-Site date when a schedule loading is applied.
- Extract commercial terms (price, spares, freight, delivery, payment terms, warranty, Incoterms)
  from the supplier bid documents; never invent a term that is not in the bid.
"""


def doc_tbe_template() -> str:
    return f"""
# Technical Bid Evaluation — Output Template
**Owner:** {COMPANY_SHORT} Engineering · **Doc type:** spec

Use this structure when producing a TBE for a tagged equipment RFQ.

```
TECHNICAL BID EVALUATION
RFQ:               <rfq_id>  ·  Tag: <equipment_tag>  ·  Category: <material_category>
Project:           <project name> (<project_id>)      ·  Required-On-Site: <yyyy-mm-dd>

Compliance matrix (per bidder):
| Requirement | Required value | Mandatory | <Supplier A> | <Supplier B> | ... |
|-------------|----------------|-----------|--------------|--------------|-----|
| ...         | ...            | Y/N       | Compliant    | Exception    | ... |

Roll-up (per bidder):
| Supplier | Technical Score | Deviations | Exceptions | TBE Status | Qualified? |

Recommendation:
  Technically qualified: <suppliers>.  Disqualified: <supplier> — <mandatory requirement not met>.
```

Rules: gate on mandatory Exceptions first; quote the Technical Score; name each disqualifying
requirement.
"""


def doc_cbe_template() -> str:
    return f"""
# Commercial Bid Evaluation — Output Template
**Owner:** {COMPANY_SHORT} Procurement · **Doc type:** spec

Use this structure when producing a CBE for the technically-qualified bids.

```
COMMERCIAL BID EVALUATION
RFQ:               <rfq_id>  ·  Tag: <equipment_tag>  ·  Category: <material_category>

Commercial comparison (technically-qualified bids only):
| Supplier | Quoted | Spares | Freight | Delivery (wk) | Payment | Warranty | Incoterms | Loadings | Evaluated |

Recommendation:
  Award:      <supplier> — Evaluated <$>, Quoted <$>  (Rank 1, technically <status>)
  Alternate:  <supplier> — Evaluated <$>
  Note:       Lowest quoted bid was <$ supplier>, DISQUALIFIED (<reason>) / or higher evaluated cost.
```

Rules: rank qualified bids by Evaluated Price; always contrast lowest quoted vs recommended evaluated.
"""


def doc_rfq_datasheet(b) -> str:
    r = b["rfq"]
    lines = "\n".join(
        f"| {q['requirement']} | {q['required_value']}{(' ' + q['unit']) if q['unit'] else ''} | "
        f"{'Yes' if q['mandatory'] else 'No'} | {q['weight']} |"
        for q in b["requirements"])
    return f"""
# {r['rfq_id']} — Technical Datasheet ({r['equipment_tag']})
**Project:** {b['project_name']} ({r['project_id']}) · **Client:** {b['client']}
**Category:** {r['material_category']} · **Equipment:** {r['equipment_desc']}
**Doc type:** spec · **Required-On-Site:** {r['required_on_site']} · **Bids due:** {r['bids_due_date']}
**Engineer's estimate:** ${r['engineers_estimate']:,.0f}

This datasheet defines the technical requirements bidders must meet for tagged equipment
**{r['equipment_tag']}**. Mandatory requirements gate technical qualification — an Exception on any
mandatory line makes a bid Non-Compliant regardless of price (see the TBE Standard).

## Technical requirements
| Requirement | Required value | Mandatory | Weight |
|---|---|---|---|
{lines}

## Notes
- Bidders shall state compliance (Compliant / Deviation / Exception) against every line above.
- Deviations must be described and are carried into the Commercial Bid Evaluation as price loadings.
"""


def doc_supplier_quotation(b, bid) -> str:
    r = b["rfq"]
    devtxt = "\n".join(
        f"- **{d['requirement']}** ({'mandatory' if d['mandatory'] else 'non-mandatory'}): "
        f"{'deviation offered against' if d['compliance'] == 'Deviation' else 'not offered / not addressed for'} "
        f"required value '{d['required_value']}'."
        for d in bid["deviations"]) or "- No technical deviations; the offer is fully compliant with the datasheet."
    total_price = bid["quoted_price"] + bid["spares_price"] + bid["freight_price"]
    return f"""
# Supplier Quotation — {bid['supplier_name']} — {r['rfq_id']} ({r['equipment_tag']})
**Doc type:** supplier_bid · **Project:** {b['project_name']} ({r['project_id']})
**Category:** {r['material_category']} · **Equipment:** {r['equipment_desc']}

{bid['supplier_name']} is pleased to submit its proposal for tagged equipment {r['equipment_tag']}.

## Commercial terms & pricing
| Item | Value |
|---|---|
| Base equipment price | ${bid['quoted_price']:,.0f} |
| Recommended spare parts | ${bid['spares_price']:,.0f} |
| Freight | ${bid['freight_price']:,.0f} |
| **Total quoted (base + spares + freight)** | **${total_price:,.0f}** |
| Delivery (ex-works to on-site) | {bid['delivery_weeks']} weeks |
| Payment terms | {bid['payment_advance_pct']}% advance / balance on delivery |
| Warranty | {bid['warranty_months']} months |
| Incoterms | {bid['incoterms']} |
| Currency | USD |

## Technical compliance statement
Overall technical status per {COMPANY_SHORT} evaluation: **{bid['tbe_status']}**
(Technical Score {bid['technical_score']}).
{devtxt}

## Validity
This quotation is valid for 60 days from the bid due date ({r['bids_due_date']}). Prices are firm and
fixed for the stated delivery. All work complies with the applicable international codes except where a
deviation is explicitly noted above.
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate the synthetic unstructured corpus.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Generated data dir (out/).")
    ap.add_argument("--docs", type=Path, default=DEFAULT_DOCS, help="Docs output dir (docs/).")
    args = ap.parse_args(argv)

    frames, manifest = _load(args.out)
    f = _falcon_facts(frames, manifest)
    b = _bid_facts(frames, manifest)
    d = args.docs

    print(f"Generating unstructured corpus in {d.resolve()} ...")
    write(d / "standards" / "mpr_authoring_standard.md", doc_authoring_standard())
    write(d / "standards" / "schedule_risk_policy.md", doc_schedule_risk_policy())
    write(d / "specs" / "change_notice_template.md", doc_change_notice_template())
    write(d / "specs" / "project_falcon_scope.md", doc_falcon_scope(f))
    write(d / "prior_reports" / "PRJ-001_MPR_2026-05.md", doc_prior_mpr_older(f))
    write(d / "prior_reports" / "PRJ-001_MPR_2026-06.md", doc_prior_mpr_recent(f))

    # ---- Bid evaluation (TBE / CBE) corpus ----
    write(d / "standards" / "tbe_evaluation_standard.md", doc_tbe_standard())
    write(d / "standards" / "cbe_evaluation_standard.md", doc_cbe_standard())
    write(d / "specs" / "tbe_output_template.md", doc_tbe_template())
    write(d / "specs" / "cbe_output_template.md", doc_cbe_template())
    rfq_id = b["rfq"]["rfq_id"]
    write(d / "specs" / f"{rfq_id}_datasheet.md", doc_rfq_datasheet(b))
    # Supplier quotation documents for the hero RFQ (the CBE "extract terms from bid docs" source):
    # include the recommended, the disqualified lowest-quote, and the alternate.
    wanted = {"Recommended", "Disqualified", "Alternate"}
    bid_docs = []
    for bid in b["bidders"]:
        if bid["award_status"] in wanted:
            fname = f"{rfq_id}_{bid['supplier_id']}_quotation.md"
            write(d / "bids" / fname, doc_supplier_quotation(b, bid))
            bid_docs.append({"title": f"{bid['supplier_name']} Quotation — {rfq_id}",
                             "doc_type": "supplier_bid", "project_id": b["rfq"]["project_id"],
                             "path": f"bids/{fname}"})

    # A tiny corpus index to aid the AI Search field mapping / ingestion.
    index = [
        {"title": "MPR Authoring Standard", "doc_type": "standard", "project_id": None,
         "path": "standards/mpr_authoring_standard.md"},
        {"title": "Schedule-Risk Classification & Escalation Policy", "doc_type": "standard",
         "project_id": None, "path": "standards/schedule_risk_policy.md"},
        {"title": "Change-Notice Template", "doc_type": "spec", "project_id": None,
         "path": "specs/change_notice_template.md"},
        {"title": "Project Falcon Scope Summary", "doc_type": "spec", "project_id": "PRJ-001",
         "path": "specs/project_falcon_scope.md"},
        {"title": "Project Falcon MPR 2026-05", "doc_type": "prior_report", "project_id": "PRJ-001",
         "path": "prior_reports/PRJ-001_MPR_2026-05.md"},
        {"title": "Project Falcon MPR 2026-06", "doc_type": "prior_report", "project_id": "PRJ-001",
         "path": "prior_reports/PRJ-001_MPR_2026-06.md"},
        {"title": "Technical Bid Evaluation (TBE) Standard", "doc_type": "standard",
         "project_id": None, "path": "standards/tbe_evaluation_standard.md"},
        {"title": "Commercial Bid Evaluation (CBE) Standard", "doc_type": "standard",
         "project_id": None, "path": "standards/cbe_evaluation_standard.md"},
        {"title": "TBE Output Template", "doc_type": "spec", "project_id": None,
         "path": "specs/tbe_output_template.md"},
        {"title": "CBE Output Template", "doc_type": "spec", "project_id": None,
         "path": "specs/cbe_output_template.md"},
        {"title": f"RFQ {rfq_id} Technical Datasheet ({b['rfq']['equipment_tag']})",
         "doc_type": "spec", "project_id": b["rfq"]["project_id"],
         "path": f"specs/{rfq_id}_datasheet.md"},
    ] + bid_docs
    (d / "corpus_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"  wrote {(d / 'corpus_index.json').name}")
    print(f"\nCorpus complete: {len(index)} documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
