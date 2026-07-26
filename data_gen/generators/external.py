"""External disruption signals: ext_disruption_signal (optional / Web-IQ style).

Origin system (narrative): external / web. Coarse external events (supplier, region,
weather, logistics) that can corroborate a project's risk. Kept small and optional.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .common import GenContext, REGIONS, iso, weighted_pick

_EVENT_TYPES = ["Supplier financial distress", "Port congestion", "Severe weather",
                "Labor action", "Customs delay", "Raw material shortage",
                "Logistics carrier disruption"]


def generate(ctx: GenContext) -> None:
    suppliers = ctx.get("sap_supplier")
    n = int(ctx.config["disruption_signal_count"])
    today = ctx.today

    rows = []
    for i in range(n):
        scope_kind = ctx.rng.choice(["supplier", "region"])
        if scope_kind == "supplier":
            scope = str(ctx.rng.choice(suppliers["supplier_id"].to_numpy()))
        else:
            scope = str(ctx.rng.choice(REGIONS))
        event_date = today - timedelta(days=int(ctx.rng.integers(0, 120)))
        rows.append({
            "signal_id": f"SIG-{i + 1:04d}",
            "scope": scope,
            "scope_kind": scope_kind,
            "event_type": ctx.rng.choice(_EVENT_TYPES),
            "event_date": iso(event_date),
            "severity": weighted_pick(ctx, {"Low": 0.5, "Medium": 0.35, "High": 0.15}, 1)[0],
            "origin_system": "external",
        })

    ctx.add("ext_disruption_signal", pd.DataFrame(rows))
