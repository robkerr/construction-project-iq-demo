"""Work Breakdown Structure: dim_wbs.

Origin system (narrative): non-SAP — Project Controls & Estimating (PC&E).
Every WBS belongs to one project and carries a discipline. wbs_id is the load-bearing
key that later lets SAP cost/procurement join to non-SAP schedule.
"""
from __future__ import annotations

import pandas as pd

from .common import GenContext, DISCIPLINES

_AREAS = ["Unit 100", "Unit 200", "Unit 300", "Offsites", "Utilities",
          "Substation", "Pipe Rack", "Control Building", "Tank Farm", "Jetty"]


def generate(ctx: GenContext) -> None:
    projects = ctx.get("dim_project")
    lo = int(ctx.config["wbs_per_project_min"])
    hi = int(ctx.config["wbs_per_project_max"])

    rows = []
    counter = 1
    for pid in projects["project_id"]:
        k = int(ctx.rng.integers(lo, hi + 1))
        for _ in range(k):
            disc = ctx.rng.choice(DISCIPLINES)
            area = ctx.rng.choice(_AREAS)
            rows.append({
                "wbs_id": f"WBS-{counter:05d}",
                "project_id": pid,
                "wbs_name": f"{area} - {disc}",
                "discipline": disc,
                "origin_system": "non-SAP",
            })
            counter += 1

    ctx.add("dim_wbs", pd.DataFrame(rows))
