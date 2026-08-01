"""Shared context, loaders, and writers for the external-source generators.

Deterministic off seed 42 (same anchor as the core generators) so the demo is
byte-identical across rebuilds. Reads the core ``out/csv`` dimensions to reuse
real project/wbs/supplier/equipment keys.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from faker import Faker

# Repo layout: external_sources/generators/base.py -> repo root is parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_CSV = REPO_ROOT / "out" / "csv"
OUT_ROOT = REPO_ROOT / "external_sources" / "out"

SEED = 42
TODAY = date(2026, 8, 1)

# Origin-system tags (surface how each source reaches OneLake).
ORIGIN_BIGQUERY = "GCP-BigQuery"
ORIGIN_SQLSERVER = "OnPrem-SQLServer"
ORIGIN_S3 = "External-Gov-S3"

# Asset class inferred from the equipment_tag prefix used in the core model.
TAG_CLASS = {
    "ET": "Electrical Equipment",
    "HX": "Heat Exchanger",
    "P": "Centrifugal Pump",
}

CRAFTS = ["Pipefitter", "Electrician", "Welder", "Millwright", "Boilermaker",
          "Ironworker", "Instrument Tech", "Operator", "Laborer", "Carpenter"]

LABOR_CLASSES = ["Apprentice", "Journeyman", "Foreman", "General Foreman", "Superintendent"]


@dataclass
class ExtContext:
    """Carries RNG, faker, the 'today' anchor, and the loaded core dimensions."""

    rng: np.random.Generator
    faker: Faker
    today: date
    dims: Dict[str, pd.DataFrame] = field(default_factory=dict)
    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)

    def add(self, name: str, df: pd.DataFrame) -> pd.DataFrame:
        self.frames[name] = df
        return df

    # ---- convenience accessors on core dims ----
    @property
    def projects(self) -> pd.DataFrame:
        return self.dims["dim_project"]

    @property
    def wbs(self) -> pd.DataFrame:
        return self.dims["dim_wbs"]

    @property
    def suppliers(self) -> pd.DataFrame:
        return self.dims["sap_supplier"]

    @property
    def rfq(self) -> pd.DataFrame:
        return self.dims["dim_rfq"]


def make_context() -> ExtContext:
    if not CORE_CSV.exists():
        raise SystemExit(
            f"Core data not found at {CORE_CSV}. Run 'python data_gen/generate.py' first."
        )
    rng = np.random.default_rng(SEED)
    faker = Faker("en_US")
    faker.seed_instance(SEED)
    dims = {}
    for name in ("dim_project", "dim_wbs", "sap_supplier", "dim_rfq"):
        dims[name] = pd.read_csv(CORE_CSV / f"{name}.csv")
    return ExtContext(rng=rng, faker=faker, today=TODAY, dims=dims)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ids(prefix: str, n: int, start: int = 1, width: int | None = None) -> list[str]:
    if width is None:
        width = max(len(str(start + n - 1)), 3)
    return [f"{prefix}{i:0{width}d}" for i in range(start, start + n)]


def weighted_pick(ctx: ExtContext, mapping: dict, size: int) -> np.ndarray:
    keys = list(mapping.keys())
    probs = np.array(list(mapping.values()), dtype=float)
    probs = probs / probs.sum()
    return ctx.rng.choice(keys, size=size, p=probs)


def rand_dates(ctx: ExtContext, start: date, end: date, size: int) -> list[date]:
    span = max((end - start).days, 1)
    offsets = ctx.rng.integers(0, span + 1, size=size)
    return [start + timedelta(days=int(o)) for o in offsets]


def iso(d) -> str | None:
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return None
    if isinstance(d, (datetime,)):
        return d.isoformat(sep=" ")
    return d.isoformat()


def money(values) -> np.ndarray:
    return np.round(np.asarray(values, dtype=float), 2)


def asset_class_for(tag: str) -> str:
    prefix = tag.split("-", 1)[0]
    return TAG_CLASS.get(prefix, "General Equipment")


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------

def write_parquet(df: pd.DataFrame, subdir: str, table: str) -> Path:
    """Write one parquet file under external_sources/out/<subdir>/<table>/."""
    folder = OUT_ROOT / subdir / table
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{table}.parquet"
    df.to_parquet(path, index=False)
    return path


def write_csv(df: pd.DataFrame, subdir: str, table: str) -> Path:
    folder = OUT_ROOT / subdir
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{table}.csv"
    df.to_csv(path, index=False)
    return path
