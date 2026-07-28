"""Bid evaluation generators — Technical Bid Evaluation (TBE) + Commercial Bid Evaluation (CBE).

Produces four referentially-consistent tables that support the two procurement use cases:

  dim_rfq                (SAP MM sourcing) — the inquiry / bid package for a tagged equipment item
  dim_tech_requirement   (non-SAP, Engineering) — the technical datasheet requirements per category
  fact_bid               (SAP MM sourcing) — one supplier bid per RFQ, with TBE + CBE roll-ups
  fact_bid_tech_eval     (non-SAP, Engineering) — the per-requirement TBE compliance matrix

The fusion story mirrors the schedule-risk demo: the **technical** evaluation is an Engineering
(non-SAP) activity, the **commercial** evaluation is a Procurement (SAP) activity, and the award
recommendation only makes sense when the two are seen together — the lowest *quoted* bid is not the
lowest *evaluated* bid once technical compliance and delivery are normalized.

A deterministic hero RFQ (RFQ-0001, a 230 kV power transformer for Project Falcon) hard-codes the
"cheapest bid is technically non-compliant and from a High-risk supplier" narrative, tying the
bid-evaluation story back to the same High-risk supplier that drives Falcon's late long-lead PO.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .common import GenContext, ids

# ---------------------------------------------------------------------------
# Material categories, tag prefixes, and the technical datasheet requirements.
# All values are generic engineering standards (ASME / API / IEC / IEEE) — no
# customer-specific content. weight = importance; mandatory reqs gate qualification.
# ---------------------------------------------------------------------------

CATEGORIES = ["Heat Exchanger", "Centrifugal Pump", "Electrical Equipment"]

TAG_PREFIX = {
    "Heat Exchanger": "HX",
    "Centrifugal Pump": "P",
    "Electrical Equipment": "ET",
}

EQUIPMENT_DESC = {
    "Heat Exchanger": "Shell & tube heat exchanger (TEMA type BEM)",
    "Centrifugal Pump": "Between-bearings centrifugal pump (API 610 BB2)",
    "Electrical Equipment": "Power transformer (230/34.5 kV, ONAN/ONAF)",
}

# (requirement, required_value, unit, weight, is_mandatory)
REQUIREMENTS = {
    "Heat Exchanger": [
        ("Design code", "ASME Sec VIII Div 1", "", 5, True),
        ("TEMA class", "TEMA R", "", 3, True),
        ("Shell material", "SA-516 Gr 70N", "", 3, False),
        ("Tube material", "SA-179 / SS304L", "", 3, False),
        ("Design pressure (shell/tube)", "150 / 300", "psig", 4, False),
        ("Design temperature", "650", "degF", 3, False),
        ("Heat transfer area", "4,500", "sqft", 4, False),
        ("Corrosion allowance", "3.0", "mm", 2, False),
        ("Radiography", "100% RT", "", 4, True),
        ("NACE MR0175 compliance", "Compliant", "", 3, True),
    ],
    "Centrifugal Pump": [
        ("Design standard", "API 610 12th Ed", "", 5, True),
        ("Pump type", "BB2 between-bearings", "", 3, False),
        ("Rated flow", "1,200", "m3/h", 4, False),
        ("Rated head", "210", "m", 4, False),
        ("NPSH required", "<= 4.5", "m", 4, False),
        ("Mechanical seal plan", "API 682 Plan 53B", "", 4, True),
        ("Casing material", "A216 WCC / 12Cr", "", 3, False),
        ("Driver", "2,500 kW induction motor", "", 3, False),
        ("Hydraulic efficiency", ">= 78", "%", 3, False),
        ("Vibration limits", "API 610 Table 9", "", 4, True),
    ],
    "Electrical Equipment": [
        ("Design standard", "IEC 60076 / IEEE C57", "", 5, True),
        ("Rated power", "60 MVA ONAN/ONAF", "", 4, False),
        ("Voltage ratio", "230 / 34.5", "kV", 4, False),
        ("Vector group", "YNd1", "", 2, False),
        ("Impedance", "12.5", "%", 3, False),
        ("Insulation level (BIL)", "1050", "kV", 4, True),
        ("Cooling", "ONAN/ONAF", "", 2, False),
        ("On-load tap changer", "OLTC +/-10%", "", 3, False),
        ("Load-loss guarantee", "<= 210", "kW", 3, False),
        ("Type test certificate", "KEMA / CESI type tested", "", 5, True),
    ],
}

# TBE compliance -> scoring factor and CBE per-deviation normalization loading ($).
COMPLIANCE_FACTOR = {"Compliant": 1.0, "Deviation": 0.6, "Exception": 0.0}
DEVIATION_LOADING = 40_000            # $ added to evaluated price per technical deviation
COMMERCIAL_DEV_LOADING = 25_000       # $ added per commercial-terms deviation
INCOTERMS = ["EXW", "FOB", "CIF", "DDP"]

# Bidder "quality" tiers drive the compliance distribution of a randomly-generated bid.
# p = (P(Compliant), P(Deviation), P(Exception)) applied to non-mandatory requirements;
# mandatory requirements use a much tighter distribution so most bids remain qualifiable.
QUALITY_TIERS = {
    "strong":   dict(opt=(0.90, 0.10, 0.00), man=(0.98, 0.02, 0.00), price=1.02, weeks=(44, 50)),
    "balanced": dict(opt=(0.72, 0.24, 0.04), man=(0.94, 0.06, 0.00), price=0.98, weeks=(46, 56)),
    "aggressive": dict(opt=(0.55, 0.30, 0.15), man=(0.82, 0.12, 0.06), price=0.88, weeks=(52, 64)),
}


# ---------------------------------------------------------------------------
# Category price anchors (engineer's estimate) — used to size quotes realistically.
# ---------------------------------------------------------------------------
CATEGORY_ESTIMATE = {
    "Heat Exchanger": 1_150_000,
    "Centrifugal Pump": 780_000,
    "Electrical Equipment": 4_600_000,
}


def _high_risk_supplier(ctx: GenContext) -> str:
    """Same deterministic High-risk supplier that seed_scenario ties Falcon's late PO to."""
    sup = ctx.get("sap_supplier")
    high = sorted(sup[sup["risk_rating"] == "High"]["supplier_id"].tolist())
    return high[0] if high else sorted(sup["supplier_id"].tolist())[0]


def _suppliers_by_rating(ctx: GenContext) -> dict:
    sup = ctx.get("sap_supplier")
    return {r: sorted(sup[sup["risk_rating"] == r]["supplier_id"].tolist())
            for r in ["Low", "Medium", "High"]}


def _requirements_frame(ctx: GenContext) -> pd.DataFrame:
    rows = []
    for cat in CATEGORIES:
        prefix = {"Heat Exchanger": "HX", "Centrifugal Pump": "PU", "Electrical Equipment": "EL"}[cat]
        for i, (req, val, unit, weight, mand) in enumerate(REQUIREMENTS[cat], start=1):
            rows.append({
                "req_id": f"REQ-{prefix}-{i:02d}",
                "material_category": cat,
                "requirement": req,
                "required_value": val,
                "unit": unit,
                "weight": weight,
                "is_mandatory": bool(mand),
                "origin_system": "non-SAP",
            })
    return pd.DataFrame(rows)


def _compliance_for(ctx: GenContext, tier: dict, mandatory: bool) -> str:
    p = tier["man"] if mandatory else tier["opt"]
    return str(ctx.rng.choice(["Compliant", "Deviation", "Exception"], p=list(p)))


def _quoted_value(required: str, compliance: str) -> str:
    if compliance == "Compliant":
        return required
    if compliance == "Deviation":
        return f"Deviation offered vs '{required}'"
    return "Not offered / not addressed"


def _score_and_qualify(evals: list[dict], reqs: pd.DataFrame) -> dict:
    """Roll a bid's per-requirement evaluation into TBE score, counts, status, qualification."""
    wsum = 0.0
    wscore = 0.0
    comp = dev = exc = 0
    mandatory_exception = False
    for e in evals:
        w = float(reqs.loc[reqs["req_id"] == e["req_id"], "weight"].iloc[0])
        wsum += w
        wscore += w * COMPLIANCE_FACTOR[e["compliance"]]
        if e["compliance"] == "Compliant":
            comp += 1
        elif e["compliance"] == "Deviation":
            dev += 1
        else:
            exc += 1
            if e["is_mandatory"]:
                mandatory_exception = True
    score = round(100.0 * wscore / wsum, 1) if wsum else 0.0
    if mandatory_exception or score < 70:
        status, qualified = "Non-Compliant", False
    elif dev > 0:
        status, qualified = "Compliant with Deviations", True
    else:
        status, qualified = "Compliant", True
    return dict(technical_score=score, tech_compliant_count=comp, tech_deviation_count=dev,
                tech_exception_count=exc, tbe_status=status, is_technically_qualified=qualified)


def _evaluated_price(quoted, spares, freight, tech_dev, comm_dev, weeks_late,
                     advance_pct, warranty_months, sched_cost_per_week) -> tuple:
    base = quoted + spares + freight
    loading = (tech_dev * DEVIATION_LOADING
               + comm_dev * COMMERCIAL_DEV_LOADING
               + max(weeks_late, 0) * sched_cost_per_week
               + round(quoted * (max(advance_pct - 10, 0) / 100.0) * 0.06, 2)   # cost of advance payment
               + (35_000 if warranty_months < 18 else 0))                        # short-warranty loading
    return round(base + loading, 2), round(loading, 2)


# ---------------------------------------------------------------------------
# Hero RFQ (Project Falcon, 230 kV transformer) — hand-crafted 4-bidder story.
# ---------------------------------------------------------------------------
def _hero_bidders(ctx: GenContext) -> list[dict]:
    by_rating = _suppliers_by_rating(ctx)
    high = _high_risk_supplier(ctx)
    low = [s for s in by_rating["Low"] if s != high]
    med = [s for s in by_rating["Medium"] if s != high] or low
    reqs = REQUIREMENTS["Electrical Equipment"]

    def comp(overrides: dict) -> list[str]:
        """Compliance vector for the 10 electrical requirements; default Compliant."""
        out = []
        for i, (req, *_rest) in enumerate(reqs, start=1):
            out.append(overrides.get(i, "Compliant"))
        return out

    return [
        # 1) Recommended — fully compliant, mid price, on-time delivery, strong warranty.
        dict(role="recommended", supplier_id=low[0], quoted=4_200_000, spares=120_000,
             freight=80_000, weeks=46, advance=10, warranty=24, incoterms="CIF",
             comm_dev=0, compliance=comp({})),
        # 2) Lowest quoted BUT technically non-compliant (missing mandatory type-test cert +
        #    BIL/loss deviations), High-risk supplier, delivery well past need-by.
        dict(role="disqualified", supplier_id=high, quoted=3_600_000, spares=90_000,
             freight=70_000, weeks=58, advance=30, warranty=12, incoterms="EXW",
             comm_dev=3, compliance=comp({6: "Deviation", 9: "Deviation", 10: "Exception"})),
        # 3) Compliant but highest price and long lead.
        dict(role="expensive", supplier_id=med[0], quoted=4_900_000, spares=140_000,
             freight=90_000, weeks=54, advance=15, warranty=24, incoterms="DDP",
             comm_dev=1, compliance=comp({})),
        # 4) Alternate — compliant with one minor deviation, competitive price.
        dict(role="alternate", supplier_id=low[1] if len(low) > 1 else low[0], quoted=4_350_000,
             spares=130_000, freight=85_000, weeks=48, advance=10, warranty=24, incoterms="CIF",
             comm_dev=0, compliance=comp({5: "Deviation"})),
    ]


def generate(ctx: GenContext) -> None:
    cfg = ctx.config.get("bid_eval", {})
    sched_cost = float(cfg.get("schedule_cost_per_week", 45_000))
    today = ctx.today
    proj = ctx.get("dim_project")
    wbs = ctx.get("dim_wbs")
    sup = ctx.get("sap_supplier")
    sup_name = sup.set_index("supplier_id")["supplier_name"].to_dict()

    reqs_df = _requirements_frame(ctx)
    ctx.add("dim_tech_requirement", reqs_df)

    rfq_rows, bid_rows, eval_rows = [], [], []
    bid_seq = 1
    eval_seq = 1
    tag_counter = {c: 1 for c in CATEGORIES}

    def _emit_rfq(rfq_id, project_id, category, bidders_spec, ros_days, estimate,
                  hero=False) -> None:
        """bidders_spec: list of dicts with at least supplier_id + compliance vector; the rest of
        the commercial terms are either provided (hero) or drawn from a quality tier."""
        nonlocal bid_seq, eval_seq
        pwbs = wbs[wbs["project_id"] == project_id]
        wbs_id = sorted(pwbs["wbs_id"].tolist())[0] if len(pwbs) else wbs["wbs_id"].iloc[0]
        tag = f"{TAG_PREFIX[category]}-{1000 + tag_counter[category]:04d}"
        tag_counter[category] += 1
        issued = today - timedelta(days=ros_days + int(ctx.rng.integers(40, 90)))
        due = issued + timedelta(days=int(ctx.rng.integers(21, 45)))
        ros = today + timedelta(days=int(ctx.rng.integers(60, 260))) if not hero else \
            due + timedelta(weeks=50)     # hero need-by = 50 weeks after bids due
        cat_reqs = reqs_df[reqs_df["material_category"] == category].reset_index(drop=True)

        computed = []
        for spec in bidders_spec:
            sid = spec["supplier_id"]
            compliance_vec = spec["compliance"]
            evals = []
            for i, r in cat_reqs.iterrows():
                c = compliance_vec[i]
                evals.append({
                    "eval_id": f"TEV-{eval_seq:05d}",
                    "bid_id": f"BID-{bid_seq:05d}",
                    "rfq_id": rfq_id,
                    "supplier_id": sid,
                    "req_id": r["req_id"],
                    "requirement": r["requirement"],
                    "required_value": r["required_value"],
                    "quoted_value": _quoted_value(r["required_value"], c),
                    "compliance": c,
                    "is_mandatory": bool(r["is_mandatory"]),
                    "comment": ("Meets specification" if c == "Compliant"
                                else "Technical deviation — requires normalization" if c == "Deviation"
                                else "Mandatory requirement not met" if r["is_mandatory"]
                                else "Requirement not addressed"),
                    "origin_system": "non-SAP",
                })
                eval_seq += 1
            roll = _score_and_qualify(evals, cat_reqs)

            weeks = int(spec.get("weeks") or int(ctx.rng.integers(*spec["tier"]["weeks"])))
            weeks_late = max(weeks - int(round(ros_days / 7)), 0) if hero else \
                max(weeks - int(round((ros - due).days / 7)), 0)
            quoted = float(spec.get("quoted") or round(
                estimate * spec["tier"]["price"] * (1 + ctx.rng.uniform(-0.06, 0.10)), -3))
            spares = float(spec.get("spares") or round(quoted * ctx.rng.uniform(0.025, 0.05), -3))
            freight = float(spec.get("freight") or round(quoted * ctx.rng.uniform(0.015, 0.03), -3))
            advance = int(spec.get("advance") or int(ctx.rng.choice([10, 15, 20, 30])))
            warranty = int(spec.get("warranty") or int(ctx.rng.choice([12, 18, 24, 24, 36])))
            incoterms = spec.get("incoterms") or str(ctx.rng.choice(INCOTERMS))
            comm_dev = int(spec.get("comm_dev", int(ctx.rng.integers(0, 3))))

            evaluated, loading = _evaluated_price(
                quoted, spares, freight, roll["tech_deviation_count"], comm_dev,
                weeks_late, advance, warranty, sched_cost)

            computed.append(dict(
                bid_id=f"BID-{bid_seq:05d}", supplier_id=sid, evals=evals, roll=roll,
                quoted=quoted, spares=spares, freight=freight, delivery_weeks=weeks,
                weeks_late=weeks_late, advance=advance, warranty=warranty, incoterms=incoterms,
                comm_dev=comm_dev, evaluated=evaluated, loading=loading, wbs_id=wbs_id, tag=tag))
            bid_seq += 1

        # ---- CBE: rank technically-qualified bids by evaluated price; recommend the lowest ----
        qualified = sorted([c for c in computed if c["roll"]["is_technically_qualified"]],
                           key=lambda c: c["evaluated"])
        rank_of = {c["bid_id"]: i + 1 for i, c in enumerate(qualified)}
        for c in computed:
            r = rank_of.get(c["bid_id"])
            if not c["roll"]["is_technically_qualified"]:
                award, recommended = "Disqualified", False
            elif r == 1:
                award, recommended = "Recommended", True
            elif r == 2:
                award, recommended = "Alternate", False
            else:
                award, recommended = "Not Recommended", False
            bid_rows.append({
                "bid_id": c["bid_id"], "rfq_id": rfq_id, "project_id": project_id,
                "wbs_id": c["wbs_id"], "equipment_tag": tag, "material_category": category,
                "supplier_id": c["supplier_id"], "supplier_name": sup_name.get(c["supplier_id"], ""),
                "bid_date": (due - timedelta(days=int(ctx.rng.integers(1, 10)))).isoformat(),
                "currency": "USD",
                "quoted_price": c["quoted"], "spares_price": c["spares"], "freight_price": c["freight"],
                "delivery_weeks": c["delivery_weeks"], "weeks_late": c["weeks_late"],
                "payment_advance_pct": c["advance"], "warranty_months": c["warranty"],
                "incoterms": c["incoterms"],
                "technical_score": c["roll"]["technical_score"],
                "tech_compliant_count": c["roll"]["tech_compliant_count"],
                "tech_deviation_count": c["roll"]["tech_deviation_count"],
                "tech_exception_count": c["roll"]["tech_exception_count"],
                "tbe_status": c["roll"]["tbe_status"],
                "is_technically_qualified": c["roll"]["is_technically_qualified"],
                "commercial_deviation_count": c["comm_dev"],
                "evaluated_price": c["evaluated"], "price_loading": c["loading"],
                "cbe_rank": int(r) if r else 0,
                "award_status": award, "recommended": recommended,
                "origin_system": "SAP",
            })
            eval_rows.extend(c["evals"])

        rfq_rows.append({
            "rfq_id": rfq_id, "project_id": project_id, "wbs_id": wbs_id,
            "equipment_tag": tag, "material_category": category,
            "equipment_desc": EQUIPMENT_DESC[category],
            "engineers_estimate": float(estimate), "currency": "USD",
            "issued_date": issued.isoformat(), "bids_due_date": due.isoformat(),
            "required_on_site": ros.isoformat(),
            "status": "Under Evaluation" if not hero else "Under Evaluation",
            "bidder_count": len(computed), "origin_system": "SAP",
        })

    # ---- 1) Hero RFQ-0001: Project Falcon 230 kV transformer, hand-crafted 4-bidder story ----
    hero_specs = _hero_bidders(ctx)
    _emit_rfq("RFQ-0001", ctx.config["hero"]["project_id"], "Electrical Equipment",
              hero_specs, ros_days=50 * 7, estimate=CATEGORY_ESTIMATE["Electrical Equipment"],
              hero=True)

    # ---- 2) Two more Falcon RFQs (a pump + a heat exchanger) for breadth ----
    falcon = ctx.config["hero"]["project_id"]
    for rfq_no, cat in [(2, "Centrifugal Pump"), (3, "Heat Exchanger")]:
        specs = _random_bidders(ctx, cat, sup)
        _emit_rfq(f"RFQ-{rfq_no:04d}", falcon, cat, specs,
                  ros_days=int(ctx.rng.integers(120, 260)), estimate=CATEGORY_ESTIMATE[cat])

    # ---- 3) Portfolio RFQs across the other projects ----
    other_projects = [p for p in proj["project_id"].tolist() if p != falcon]
    n_rfq = int(cfg.get("rfq_count", 9))
    for k in range(n_rfq):
        pid = str(ctx.rng.choice(other_projects))
        cat = str(ctx.rng.choice(CATEGORIES))
        specs = _random_bidders(ctx, cat, sup)
        _emit_rfq(f"RFQ-{4 + k:04d}", pid, cat, specs,
                  ros_days=int(ctx.rng.integers(120, 300)), estimate=CATEGORY_ESTIMATE[cat])

    ctx.add("dim_rfq", pd.DataFrame(rfq_rows))
    ctx.add("fact_bid", pd.DataFrame(bid_rows))
    ctx.add("fact_bid_tech_eval", pd.DataFrame(eval_rows))


def _random_bidders(ctx: GenContext, category: str, sup: pd.DataFrame) -> list[dict]:
    """Draw N bidders for a non-hero RFQ: pick suppliers + a quality tier, then a compliance vector."""
    cfg = ctx.config.get("bid_eval", {})
    lo = int(cfg.get("bidders_per_rfq_min", 3))
    hi = int(cfg.get("bidders_per_rfq_max", 5))
    n = int(ctx.rng.integers(lo, hi + 1))
    supplier_ids = sup["supplier_id"].to_numpy()
    chosen = list(pd.unique(ctx.rng.choice(supplier_ids, size=n * 2)))[:n]
    reqs = REQUIREMENTS[category]
    tiers = list(QUALITY_TIERS.values())
    tier_names = list(QUALITY_TIERS.keys())
    specs = []
    for sid in chosen:
        # Bias tier by supplier risk rating so High-risk suppliers bid more aggressively/less compliant.
        rating = sup.loc[sup["supplier_id"] == sid, "risk_rating"].iloc[0]
        if rating == "High":
            tier = QUALITY_TIERS[str(ctx.rng.choice(["aggressive", "balanced"], p=[0.6, 0.4]))]
        elif rating == "Medium":
            tier = QUALITY_TIERS[str(ctx.rng.choice(["balanced", "aggressive", "strong"], p=[0.5, 0.25, 0.25]))]
        else:
            tier = QUALITY_TIERS[str(ctx.rng.choice(["strong", "balanced"], p=[0.6, 0.4]))]
        compliance = [_compliance_for(ctx, tier, mand) for (_r, _v, _u, _w, mand) in reqs]
        specs.append(dict(supplier_id=sid, compliance=compliance, tier=tier))
    return specs
