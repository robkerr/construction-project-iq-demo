"""Project master: dim_project.

Origin system (narrative): non-SAP — Project Controls & Estimating (PC&E) master.
Twelve projects, one hero (Project Falcon, PRJ-001). Baseline is healthy; the at-risk
story is injected deterministically later in seed_scenario.py.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .common import (GenContext, CLIENTS, CONTRACT_TYPES, PROJECT_CODENAMES, REGIONS,
                     ids, iso)


def generate(ctx: GenContext) -> None:
    n = ctx.n_projects
    project_ids = ids("PRJ-", n)

    names, clients, regions, contracts = [], [], [], []
    planned_finish, forecast_finish, pct_complete, start_dates = [], [], [], []

    for i in range(n):
        codename = PROJECT_CODENAMES[i % len(PROJECT_CODENAMES)]
        names.append(f"Project {codename}")
        clients.append(CLIENTS[i % len(CLIENTS)])
        regions.append(ctx.rng.choice(REGIONS))
        contracts.append(ctx.rng.choice(CONTRACT_TYPES))

        # Mid-execution portfolio: started 12-30 months ago, finishing 3-18 months out.
        start = ctx.today - timedelta(days=int(ctx.rng.integers(360, 900)))
        start_dates.append(start)
        planned = ctx.today + timedelta(days=int(ctx.rng.integers(90, 540)))
        planned_finish.append(planned)
        # Baseline: forecast == planned (healthy). Injection will slip the hero + secondaries.
        forecast_finish.append(planned)
        pct_complete.append(round(float(ctx.rng.uniform(0.30, 0.75)), 2))

    df = pd.DataFrame({
        "project_id": project_ids,
        "project_name": names,
        "client": clients,
        "region": regions,
        "contract_type": contracts,
        "start_date": [iso(d) for d in start_dates],
        "planned_finish": [iso(d) for d in planned_finish],
        "forecast_finish": [iso(d) for d in forecast_finish],
        "pct_complete": pct_complete,
        "is_active": True,
        "origin_system": "non-SAP",
    })

    # Pin the hero project's identity and put it squarely mid-execution.
    hero = ctx.config["hero"]
    df.loc[df["project_id"] == hero["project_id"], "project_name"] = hero["project_name"]
    df.loc[df["project_id"] == hero["project_id"], "pct_complete"] = 0.55

    ctx.add("dim_project", df)
