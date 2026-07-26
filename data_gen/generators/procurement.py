"""SAP procurement purchase orders: sap_mm_po.

Origin system (narrative): SAP S/4HANA — Materials Management / procurement. Baseline
is healthy (mostly On-time, revised == promised). The Falcon late long-lead PO is
injected later in seed_scenario.py.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .common import (GenContext, COMMODITY_MATERIALS, LONG_LEAD_MATERIALS, ids,
                     iso, weighted_pick)


def generate(ctx: GenContext) -> None:
    wbs = ctx.get("dim_wbs")
    suppliers = ctx.get("sap_supplier")
    n = int(ctx.config["po_count"])
    long_lead_rate = float(ctx.config["long_lead_rate"])
    today = ctx.today

    wbs_pick = wbs.sample(n=n, replace=True, random_state=ctx.seed).reset_index(drop=True)
    supplier_ids = suppliers["supplier_id"].to_numpy()

    rows = []
    for i in range(n):
        w = wbs_pick.iloc[i]
        is_long_lead = bool(ctx.rng.random() < long_lead_rate)
        material = (ctx.rng.choice(LONG_LEAD_MATERIALS) if is_long_lead
                    else ctx.rng.choice(COMMODITY_MATERIALS))
        # Promised delivery clustered around the next 6 months from today.
        promised = today + timedelta(days=int(ctx.rng.integers(-120, 210)))
        # Healthy baseline: On-time dominates. Long-lead POs are never "Late" in the baseline,
        # so the single injected Falcon late long-lead PO is the only procurement-risk driver.
        if is_long_lead:
            status = weighted_pick(ctx, {"On-time": 0.85, "At-risk": 0.15}, 1)[0]
        else:
            status = weighted_pick(ctx, {"On-time": 0.80, "At-risk": 0.13, "Late": 0.07}, 1)[0]
        if status == "Late":
            revised = promised + timedelta(days=int(ctx.rng.integers(5, 20)))
        elif status == "At-risk":
            revised = promised + timedelta(days=int(ctx.rng.integers(1, 8)))
        else:
            revised = promised
        rows.append({
            "po_id": f"PO-{i + 1:05d}",
            "project_id": w["project_id"],
            "wbs_id": w["wbs_id"],
            "material_desc": material,
            "supplier_id": ctx.rng.choice(supplier_ids),
            "promised_date": iso(promised),
            "revised_date": iso(revised),
            "status": status,
            "is_long_lead": is_long_lead,
            "origin_system": "SAP",
        })

    ctx.add("sap_mm_po", pd.DataFrame(rows))
