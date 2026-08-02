"""Convert the S3 permit parquet tables to Delta Lake format.

OneLake shortcuts placed in a lakehouse's *Tables* section are only recognized
as queryable tables when the source is in **Delta Lake** format (a folder with a
``_delta_log``). The permit tables are generated as plain parquet, so this script
rewrites each one as a Delta table under ``external_sources/out/s3_delta/<table>/``.

The Delta folders are then uploaded to S3 by ``place_s3_delta.sh`` and shortcut
into the bronze lakehouse as true tables (``bronze.permit`` etc.).

Run:
    ./.venv/bin/python external_sources/convert_s3_to_delta.py

Deterministic: reads the committed parquet in ``out/s3/permits`` and writes Delta
with a single parquet data file per table (no data movement or randomness).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pyarrow.parquet as pq
from deltalake import write_deltalake

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "external_sources" / "out" / "s3" / "permits"
DELTA_ROOT = REPO_ROOT / "external_sources" / "out" / "s3_delta" / "permits"

TABLES = [
    "authority",
    "permit",
    "inspection",
    "code_violation",
    "permit_fee",
    "environmental_reading",
]


def convert_table(table: str) -> int:
    src = SRC_ROOT / table / f"{table}.parquet"
    if not src.exists():
        raise FileNotFoundError(f"Source parquet not found: {src}")

    dest = DELTA_ROOT / table
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    tbl = pq.read_table(src)
    write_deltalake(str(dest), tbl, mode="overwrite")
    return tbl.num_rows


def main() -> None:
    DELTA_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"Writing Delta tables to {DELTA_ROOT}\n")
    total = 0
    for table in TABLES:
        rows = convert_table(table)
        total += rows
        has_log = (DELTA_ROOT / table / "_delta_log").is_dir()
        print(f"  {table:<24} {rows:>7,} rows   _delta_log={'yes' if has_log else 'NO'}")
    print(f"\nDone. {len(TABLES)} Delta tables, {total:,} total rows.")
    print("Next: ./external_sources/place_s3_delta.sh  (uploads to S3)")


if __name__ == "__main__":
    main()
