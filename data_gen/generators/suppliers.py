"""SAP vendor master: sap_supplier.

Origin system (narrative): SAP S/4HANA — Materials Management vendor master.
"""
from __future__ import annotations

import pandas as pd

from .common import GenContext, COUNTRIES, ids, weighted_pick

_SUPPLIER_SUFFIXES = ["Industrial", "Fabrication", "Systems", "Engineered Products",
                      "Heavy Equipment", "Manufacturing", "Controls", "Power Solutions",
                      "Machinery", "Steel Works", "Instruments", "Turbomachinery"]


def generate(ctx: GenContext) -> None:
    n = int(ctx.config["supplier_count"])

    names = []
    seen = set()
    while len(names) < n:
        stem = ctx.faker.last_name()
        suffix = ctx.rng.choice(_SUPPLIER_SUFFIXES)
        name = f"{stem} {suffix}"
        if name in seen:
            continue
        seen.add(name)
        names.append(name)

    df = pd.DataFrame({
        "supplier_id": ids("SUP-", n),
        "supplier_name": names,
        "country": ctx.rng.choice(COUNTRIES, size=n),
        # Most suppliers are low/medium risk; a minority are high (procurement risk signal).
        "risk_rating": weighted_pick(ctx, {"Low": 0.55, "Medium": 0.32, "High": 0.13}, n),
        "origin_system": "SAP",
    })
    ctx.add("sap_supplier", df)
