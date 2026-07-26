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

    print(f"\nOutput written to: {args.out.resolve()}")
    print(f"Manifest: {(args.out / 'manifest.json').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
