"""Synthetic project-controls dataset generator (SAP + non-SAP).

Generates a referentially-consistent set of Parquet/CSV tables for the Contoso E&C
"Project Schedule Risk -> Monthly Progress Report" Fabric IQ demo, then injects a
deterministic "Project Falcon at-risk" story whose drivers span SAP and non-SAP systems.

Usage:
    python generate.py
    python generate.py --seed 42 --out ../out --formats parquet csv
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

# Allow running from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generators import PIPELINE            # noqa: E402
from generators.common import make_context  # noqa: E402
import seed_scenario                        # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.yaml"
DEFAULT_OUT = HERE.parent / "out"

# Foreign keys to validate (child.column -> parent.column).
FK_CHECKS = [
    ("dim_wbs", "project_id", "dim_project", "project_id"),
    ("fact_schedule_activity", "wbs_id", "dim_wbs", "wbs_id"),
    ("fact_schedule_activity", "project_id", "dim_project", "project_id"),
    ("sap_fi_cost", "wbs_id", "dim_wbs", "wbs_id"),
    ("sap_mm_po", "wbs_id", "dim_wbs", "wbs_id"),
    ("sap_mm_po", "supplier_id", "sap_supplier", "supplier_id"),
    ("fact_engineering_change", "wbs_id", "dim_wbs", "wbs_id"),
    ("dim_rfq", "project_id", "dim_project", "project_id"),
    ("dim_rfq", "wbs_id", "dim_wbs", "wbs_id"),
    ("fact_bid", "rfq_id", "dim_rfq", "rfq_id"),
    ("fact_bid", "supplier_id", "sap_supplier", "supplier_id"),
    ("fact_bid_tech_eval", "bid_id", "fact_bid", "bid_id"),
    ("fact_bid_tech_eval", "req_id", "dim_tech_requirement", "req_id"),
]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate synthetic project-controls demo data.")
    p.add_argument("--seed", type=int, default=None, help="Random seed (overrides config).")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config.yaml.")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory (out/).")
    p.add_argument("--formats", nargs="+", default=["parquet", "csv"],
                   choices=["csv", "parquet"], help="Output formats to write.")
    return p.parse_args(argv)


def load_config(path: Path, seed) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if seed is not None:
        cfg["seed"] = seed
    return cfg


def check_referential_integrity(ctx) -> list[str]:
    errors = []
    for child, ckey, parent, pkey in FK_CHECKS:
        cvals = set(ctx.get(child)[ckey].dropna().unique())
        pvals = set(ctx.get(parent)[pkey].unique())
        missing = cvals - pvals
        if missing:
            errors.append(f"{child}.{ckey} has {len(missing)} value(s) not in "
                          f"{parent}.{pkey} (e.g. {sorted(missing)[:3]})")
    # affected_activity_id (nullable) must resolve when present
    ec = ctx.get("fact_engineering_change")
    act_ids = set(ctx.get("fact_schedule_activity")["activity_id"].unique())
    bad = set(ec["affected_activity_id"].dropna().unique()) - act_ids
    if bad:
        errors.append(f"fact_engineering_change.affected_activity_id has {len(bad)} unresolved id(s)")
    return errors


def rank_projects(ctx) -> pd.DataFrame:
    """Compute a demo-style schedule-risk ranking to verify Falcon lands #1."""
    proj = ctx.get("dim_project")[["project_id", "project_name"]].copy()
    acts = ctx.get("fact_schedule_activity").copy()
    acts["bfin"] = pd.to_datetime(acts["baseline_finish"])
    acts["ffin"] = pd.to_datetime(acts["forecast_finish"])
    acts["slip"] = (acts["ffin"] - acts["bfin"]).dt.days.clip(lower=0)

    slip = acts.groupby("project_id")["slip"].max().rename("max_slip_days")
    minfloat = acts.groupby("project_id")["total_float_days"].min().rename("min_float")
    cp_risk = (acts[acts["is_critical_path"] & (acts["ffin"] > acts["bfin"])]
               .groupby("project_id").size().rename("cp_at_risk"))

    po = ctx.get("sap_mm_po")
    late_ll = (po[(po["is_long_lead"]) & (po["status"] == "Late")]
               .groupby("project_id").size().rename("late_long_lead_pos"))

    cost = ctx.get("sap_fi_cost")
    overrun = ((cost["forecast_cost"] - cost["budget"]).groupby(cost["project_id"]).sum()
               .rename("forecast_overrun"))

    out = (proj.set_index("project_id")
           .join([slip, minfloat, cp_risk, late_ll, overrun]).fillna(0))
    out["risk_score"] = (
        out["max_slip_days"] * 1.5
        + out["min_float"].apply(lambda x: -x if x < 0 else 0) * 2
        + out["cp_at_risk"] * 3
        + out["late_long_lead_pos"] * 5
        + out["forecast_overrun"] / 100_000
    ).clip(upper=100).round(1)
    return out.sort_values("risk_score", ascending=False).reset_index()


def write_frames(frames: dict, out_dir: Path, formats) -> dict:
    csv_dir = out_dir / "csv"
    pq_dir = out_dir / "parquet"
    if "csv" in formats:
        csv_dir.mkdir(parents=True, exist_ok=True)
    if "parquet" in formats:
        pq_dir.mkdir(parents=True, exist_ok=True)

    counts = {}
    for name, df in frames.items():
        counts[name] = int(len(df))
        if "csv" in formats:
            df.to_csv(csv_dir / f"{name}.csv", index=False)
        if "parquet" in formats:
            df.to_parquet(pq_dir / f"{name}.parquet", index=False)
    return counts


def bid_eval_summary(ctx) -> dict:
    """Verify the hero RFQ-0001 story: recommended bid is technically qualified and is NOT the
    lowest quoted (the lowest quoted is disqualified) — the load-bearing TBE/CBE insight."""
    bids = ctx.get("fact_bid")
    hero = bids[bids["rfq_id"] == "RFQ-0001"].copy()
    out = {"ok": False, "detail": ""}
    if hero.empty:
        out["detail"] = "RFQ-0001 has no bids"
        return out
    lowest_quoted = hero.sort_values("quoted_price").iloc[0]
    rec = hero[hero["recommended"]]
    if rec.empty:
        out["detail"] = "no recommended bid on RFQ-0001"
        return out
    rec = rec.iloc[0]
    lowest_qualified_eval = (hero[hero["is_technically_qualified"]]
                             .sort_values("evaluated_price").iloc[0])
    out["lowest_quoted_supplier"] = lowest_quoted["supplier_name"]
    out["lowest_quoted_price"] = float(lowest_quoted["quoted_price"])
    out["lowest_quoted_qualified"] = bool(lowest_quoted["is_technically_qualified"])
    out["recommended_supplier"] = rec["supplier_name"]
    out["recommended_quoted"] = float(rec["quoted_price"])
    out["recommended_evaluated"] = float(rec["evaluated_price"])
    out["ok"] = (
        bool(rec["is_technically_qualified"])                      # recommendation is qualified
        and rec["bid_id"] == lowest_qualified_eval["bid_id"]       # = lowest evaluated qualified bid
        and not bool(lowest_quoted["is_technically_qualified"])    # cheapest is disqualified
        and rec["quoted_price"] > lowest_quoted["quoted_price"]    # and not the cheapest quote
    )
    return out


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = load_config(args.config, args.seed)
    ctx = make_context(cfg)

    print(f"Generating synthetic project-controls data: {ctx.n_projects} projects, "
          f"seed={ctx.seed}, today={ctx.today.isoformat()}")

    for name, module in PIPELINE:
        module.generate(ctx)
        print(f"  [{name:20s}] ok")

    print("Injecting deterministic 'Project Falcon at-risk' scenario...")
    injections = seed_scenario.apply(ctx)

    # ---- Referential integrity ----
    errors = check_referential_integrity(ctx)
    if errors:
        print("\nREFERENTIAL INTEGRITY ERRORS:")
        for e in errors:
            print(f"  ! {e}")
        return 2
    print("Referential integrity: OK (all SAP<->non-SAP keys resolve)")

    counts = write_frames(ctx.frames, args.out, args.formats)

    # ---- Hero bid-evaluation facts (so docs_gen quotes the same numbers) ----
    bids_all = ctx.get("fact_bid")
    hero_bids = bids_all[bids_all["rfq_id"] == "RFQ-0001"]
    hero_rfq = ctx.get("dim_rfq")
    hero_rfq_row = hero_rfq[hero_rfq["rfq_id"] == "RFQ-0001"].iloc[0]
    hero_bid_eval = {
        "rfq_id": "RFQ-0001",
        "project_id": str(hero_rfq_row["project_id"]),
        "equipment_tag": str(hero_rfq_row["equipment_tag"]),
        "material_category": str(hero_rfq_row["material_category"]),
        "equipment_desc": str(hero_rfq_row["equipment_desc"]),
        "engineers_estimate": float(hero_rfq_row["engineers_estimate"]),
        "required_on_site": str(hero_rfq_row["required_on_site"]),
        "bids_due_date": str(hero_rfq_row["bids_due_date"]),
        "bids": [
            {k: (float(b[k]) if k in ("quoted_price", "evaluated_price", "technical_score") else
                 int(b[k]) if k in ("delivery_weeks", "warranty_months", "payment_advance_pct",
                                    "tech_deviation_count", "tech_exception_count") else str(b[k]))
             for k in ("supplier_name", "supplier_id", "quoted_price", "evaluated_price",
                       "technical_score", "tbe_status", "award_status", "delivery_weeks",
                       "warranty_months", "payment_advance_pct", "incoterms",
                       "tech_deviation_count", "tech_exception_count")}
            for _, b in hero_bids.sort_values("evaluated_price").iterrows()
        ],
    }

    # ---- Manifest ----
    origin = {name: (df["origin_system"].iloc[0] if "origin_system" in df.columns else "n/a")
              for name, df in ctx.frames.items()}
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": ctx.seed,
        "today": ctx.today.isoformat(),
        "formats": args.formats,
        "tables": counts,
        "origin_system": origin,
        "total_rows": int(sum(counts.values())),
        "injected_projects": injections,
        "hero_bid_eval": hero_bid_eval,
    }
    with open(args.out / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # ---- Summary ----
    print("\nRow counts by table (origin system):")
    for name in sorted(counts):
        print(f"  {name:26s} {counts[name]:>8,}   [{origin[name]}]")
    print(f"\nTotal rows: {manifest['total_rows']:,}")

    ranking = rank_projects(ctx)
    print("\nSchedule-risk ranking (top 5):")
    print("  rank  project_id  project_name        score  slip  minFloat  cpRisk  lateLLpo  overrun$")
    for i, r in ranking.head(5).iterrows():
        print(f"  {i + 1:>4}  {r['project_id']:<10}  {r['project_name']:<18}  "
              f"{r['risk_score']:>5}  {int(r['max_slip_days']):>4}  {int(r['min_float']):>7}  "
              f"{int(r['cp_at_risk']):>6}  {int(r['late_long_lead_pos']):>8}  "
              f"{r['forecast_overrun']:>10,.0f}")

    top = ranking.iloc[0]
    hero_id = cfg["hero"]["project_id"]
    if top["project_id"] == hero_id:
        print(f"\nACCEPTANCE OK: {top['project_name']} ({hero_id}) is the #1 schedule-risk project.")
    else:
        print(f"\nACCEPTANCE FAILED: expected {hero_id} #1 but got {top['project_id']}.")
        return 3

    # ---- Bid-evaluation (TBE/CBE) summary + acceptance ----
    bids = ctx.get("fact_bid")
    rfqs = ctx.get("dim_rfq")
    print(f"\nBid evaluation: {len(rfqs)} RFQs, {len(bids)} bids across "
          f"{bids['material_category'].nunique()} material categories.")
    be = bid_eval_summary(ctx)
    print("Hero RFQ-0001 (Project Falcon 230 kV transformer):")
    hero_bids = bids[bids["rfq_id"] == "RFQ-0001"].sort_values("evaluated_price")
    print("  supplier                       quoted$     evaluated$  techScore  status                     award")
    for _, b in hero_bids.iterrows():
        print(f"  {b['supplier_name'][:28]:<28}  {b['quoted_price']:>10,.0f}  "
              f"{b['evaluated_price']:>11,.0f}  {b['technical_score']:>8}  "
              f"{b['tbe_status']:<26}  {b['award_status']}")
    if be["ok"]:
        print(f"\nACCEPTANCE OK: lowest quote (${be['lowest_quoted_price']:,.0f}, "
              f"{be['lowest_quoted_supplier']}) is DISQUALIFIED; recommended award is "
              f"{be['recommended_supplier']} at ${be['recommended_quoted']:,.0f} "
              f"(${be['recommended_evaluated']:,.0f} evaluated) — lowest evaluated qualified bid.")
    else:
        print(f"\nACCEPTANCE FAILED (bid eval): {be.get('detail', be)}")
        return 4

    print(f"\nOutput written to: {args.out.resolve()}")
    print(f"Manifest: {(args.out / 'manifest.json').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
