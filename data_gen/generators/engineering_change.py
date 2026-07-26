"""Engineering-change log: fact_engineering_change.

Origin system (narrative): non-SAP — engineering-change log. Baseline changes carry
small/zero schedule impact. The Falcon EC-1207 (+18 days on a critical-path WBS) is
injected later in seed_scenario.py.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .common import GenContext, EC_TITLE_STEMS, iso, weighted_pick


def generate(ctx: GenContext) -> None:
    wbs = ctx.get("dim_wbs")
    activities = ctx.get("fact_schedule_activity")
    n = int(ctx.config["engineering_change_count"])
    today = ctx.today

    wbs_pick = wbs.sample(n=n, replace=True, random_state=ctx.seed + 1).reset_index(drop=True)

    # Map wbs_id -> list of activity_ids for affected-activity linkage.
    act_by_wbs = activities.groupby("wbs_id")["activity_id"].apply(list).to_dict()

    rows = []
    for i in range(n):
        w = wbs_pick.iloc[i]
        disc = w["discipline"]
        stem = ctx.rng.choice(EC_TITLE_STEMS).format(disc=disc)
        issued = today - timedelta(days=int(ctx.rng.integers(0, 240)))
        status = weighted_pick(ctx, {"Open": 0.35, "Approved": 0.40, "Implemented": 0.25}, 1)[0]
        # Baseline schedule impact is small (0-5 days).
        impact = int(ctx.rng.integers(0, 6))
        acts = act_by_wbs.get(w["wbs_id"], [])
        affected = ctx.rng.choice(acts) if len(acts) else None
        rows.append({
            "ec_id": f"EC-{1000 + i}",
            "project_id": w["project_id"],
            "wbs_id": w["wbs_id"],
            "title": f"{stem} {w['wbs_name']}",
            "discipline": disc,
            "issued_date": iso(issued),
            "status": status,
            "schedule_impact_days": impact,
            "affected_activity_id": affected,
            "origin_system": "non-SAP",
        })

    ctx.add("fact_engineering_change", pd.DataFrame(rows))
