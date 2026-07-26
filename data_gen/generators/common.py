"""Shared context, RNG, and helpers for the synthetic project-controls generators.

Everything is deterministic off a single seed so the "Project Falcon at-risk" story
is byte-identical across rebuilds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict

import numpy as np
import pandas as pd
from faker import Faker

# ---------------------------------------------------------------------------
# Domain reference data (generic construction / EPC — no customer-specific data)
# ---------------------------------------------------------------------------

DISCIPLINES = ["Civil", "Mechanical", "Electrical", "Piping", "I&C", "Structural", "Process"]
CONTRACT_TYPES = ["Lump Sum", "Reimbursable", "EPC", "EPCM"]
REGIONS = ["North America", "Latin America", "EMEA", "Middle East", "Asia Pacific"]

# Owner/clients: classic Microsoft fictional companies so the demo is obviously generic.
CLIENTS = [
    "Northwind Energy", "Fabrikam Chemicals", "Adventure Works Power", "Litware Refining",
    "Proseware Utilities", "Tailwind Resources", "Wide World Metals", "Contoso Ltd",
    "Fourth Coffee Bottling", "Graphic Design Institute", "Wingtip Materials", "Coho Petrochem",
]

# Generic project codenames (bird/mission style). Falcon is the hero and stays index 0.
PROJECT_CODENAMES = [
    "Falcon", "Kestrel", "Osprey", "Harrier", "Condor", "Merlin",
    "Peregrine", "Sparrow", "Albatross", "Raven", "Heron", "Kite",
]

# Long-lead engineered-equipment descriptions used on procurement POs.
LONG_LEAD_MATERIALS = [
    "Main power transformer (230kV)", "Reactor pressure vessel", "Centrifugal compressor train",
    "Steam turbine generator", "Large-bore control valve package", "Heat recovery steam generator",
    "Switchgear lineup (medium voltage)", "Structural steel main pipe rack",
    "Fired heater module", "Cooling water pump skid",
]
COMMODITY_MATERIALS = [
    "Carbon steel pipe spools", "Cable tray and fittings", "Instrument bulk materials",
    "Concrete and rebar", "Structural bolts", "Field paint and coatings",
    "Electrical conduit", "Gaskets and fasteners", "Grating and handrail", "Insulation materials",
]

COUNTRIES = ["United States", "Canada", "Germany", "United Kingdom", "Netherlands",
             "United Arab Emirates", "Saudi Arabia", "South Korea", "Japan", "Brazil", "Mexico"]

EC_TITLE_STEMS = [
    "Revised {disc} design basis for", "Client-requested scope change on",
    "Vendor deviation impacting", "Field condition rework on",
    "Regulatory update affecting", "Interface clash resolution on",
    "Material substitution for", "Constructability improvement on",
]


@dataclass
class GenContext:
    """Carries config, RNG, the 'today' anchor, and the growing set of generated frames."""

    config: dict
    seed: int
    today: date
    rng: np.random.Generator
    faker: Faker
    frames: Dict[str, pd.DataFrame] = field(default_factory=dict)

    @property
    def n_projects(self) -> int:
        return int(self.config["n_projects"])

    def add(self, name: str, df: pd.DataFrame) -> pd.DataFrame:
        self.frames[name] = df
        return df

    def get(self, name: str) -> pd.DataFrame:
        return self.frames[name]


def make_context(config: dict) -> GenContext:
    seed = int(config["seed"])
    rng = np.random.default_rng(seed)
    faker = Faker("en_US")
    faker.seed_instance(seed)
    today = _parse_date(config["today"])
    return GenContext(config=config, seed=seed, today=today, rng=rng, faker=faker)


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


# ---------- helpers ----------

def ids(prefix: str, n: int, start: int = 1, width: int = None) -> list[str]:
    if width is None:
        width = max(len(str(start + n - 1)), 3)
    return [f"{prefix}{i:0{width}d}" for i in range(start, start + n)]


def rand_dates(ctx: GenContext, start: date, end: date, size: int) -> list[date]:
    span = max((end - start).days, 1)
    offsets = ctx.rng.integers(0, span + 1, size=size)
    return [start + timedelta(days=int(o)) for o in offsets]


def weighted_pick(ctx: GenContext, mapping: dict, size: int) -> np.ndarray:
    keys = list(mapping.keys())
    probs = np.array(list(mapping.values()), dtype=float)
    probs = probs / probs.sum()
    return ctx.rng.choice(keys, size=size, p=probs)


def money(values) -> np.ndarray:
    return np.round(np.asarray(values, dtype=float), 2)


def iso(d) -> str | None:
    if d is None or (isinstance(d, float) and np.isnan(d)):
        return None
    return d.isoformat()
