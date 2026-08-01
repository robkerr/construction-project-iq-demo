"""Entrypoint: generate all three external-source datasets for the OneLake demo.

    python external_sources/generate_external.py

Reads the core seed-42 keys from out/csv, generates:
  - bigquery/  : work-order management (mirrored)        -> parquet + csv
  - sqlserver/ : time clock / labor (mirrored)           -> csv + schema.sql + load_bulk.sql
  - s3/permits : government permits & inspections (shortcut) -> parquet

Then runs referential-integrity checks against the core keys and prints a
summary + writes external_sources/out/manifest.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from generators.base import make_context, OUT_ROOT, CORE_CSV
from generators import workorders, timeclock, permits


def _fk_check(name, child: pd.DataFrame, col, parent_values, errors):
    if col not in child.columns:
        return
    vals = child[col].dropna()
    missing = set(vals.unique()) - set(parent_values)
    if missing:
        errors.append(f"  [{name}] {len(missing)} {col} values not in core: {sorted(missing)[:5]}...")


def main() -> None:
    ctx = make_context()
    print("Loaded core dimensions from", CORE_CSV)

    print("\nGenerating external sources...")
    bq = workorders.generate(ctx)
    print("  [bigquery  ] work-order management  ok")
    sql = timeclock.generate(ctx)
    print("  [sqlserver ] time clock / labor      ok")
    s3 = permits.generate(ctx)
    print("  [s3        ] permits & inspections   ok")

    all_tables = {**{f"bigquery.{k}": v for k, v in bq.items()},
                  **{f"sqlserver.{k}": v for k, v in sql.items()},
                  **{f"s3.{k}": v for k, v in s3.items()}}

    # ---- referential integrity vs core keys ----
    proj = set(ctx.projects["project_id"])
    wbs = set(ctx.wbs["wbs_id"])
    sup = set(ctx.suppliers["supplier_id"])
    errors: list[str] = []
    for key, df in all_tables.items():
        _fk_check(key, df, "project_id", proj, errors)
        _fk_check(key, df, "wbs_id", wbs, errors)
        _fk_check(key, df, "supplier_id", sup, errors)

    print("\nReferential integrity vs core keys:", "OK" if not errors else "FAILED")
    for e in errors:
        print(e)

    # ---- Falcon / hero tie-in acceptance ----
    print("\nHero tie-in checks (Project Falcon PRJ-001 / ET-1001):")
    et_assets = bq["equipment_asset"]
    print("  ET-1001 in equipment_asset:",
          "OK" if "ET-1001" in set(et_assets["equipment_tag"]) else "MISSING")
    print("  Emergency WO on ET-1001    :",
          "OK" if ((bq["work_order"].equipment_tag == "ET-1001") &
                   (bq["work_order"].wo_type == "Emergency")).any() else "MISSING")
    falcon_ts = sql["timesheet"][sql["timesheet"].project_id == "PRJ-001"]
    print(f"  Falcon timesheets          : {len(falcon_ts)} rows")
    open_crit = s3["code_violation"][(s3["code_violation"].project_id == "PRJ-001") &
                                     (s3["code_violation"].severity == "Critical") &
                                     (s3["code_violation"].status == "Open")]
    print("  Falcon open critical viol. :", "OK" if len(open_crit) else "MISSING")

    # ---- row counts + manifest ----
    print("\nRow counts by table:")
    manifest = {"seed": 42, "today": "2026-08-01", "sources": {}}
    for source in ("bigquery", "sqlserver", "s3"):
        tabs = {k.split(".", 1)[1]: v for k, v in all_tables.items() if k.startswith(source + ".")}
        manifest["sources"][source] = {t: int(len(df)) for t, df in tabs.items()}
        print(f"  {source}:")
        for t, df in tabs.items():
            print(f"    {t:<28} {len(df):>7,}")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("\nOutput written to:", OUT_ROOT)
    print("Manifest:", OUT_ROOT / "manifest.json")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
