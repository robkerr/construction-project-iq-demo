"""SAP finance cost snapshots: sap_fi_cost.

Origin system (narrative): SAP S/4HANA Finance (via RISE). One cost snapshot per WBS
per trailing month-end period. Baseline is on-budget (forecast_cost ~ budget, earned
value tracking). The Falcon overrun/exposure is injected later in seed_scenario.py.
"""
from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd

from .common import GenContext, money


def _month_end(d: date) -> date:
    first_next = (d.replace(day=1) + relativedelta(months=1))
    return first_next - relativedelta(days=1)


def generate(ctx: GenContext) -> None:
    wbs = ctx.get("dim_wbs")
    n_periods = int(ctx.config["cost_periods"])

    # Trailing month-end periods ending at the "today" anchor.
    anchor = _month_end(ctx.today - relativedelta(months=1))
    periods = [( anchor - relativedelta(months=i)).replace(day=1).isoformat()
               for i in range(n_periods)][::-1]

    rows = []
    for _, w in wbs.iterrows():
        # Each WBS has a total budget; spread/consume it across periods.
        budget_total = float(ctx.rng.integers(200_000, 4_000_000))
        pct_curve = np.linspace(0.05, 0.9, n_periods) * ctx.rng.uniform(0.9, 1.05)
        for i, period in enumerate(periods):
            frac = float(min(pct_curve[i], 1.0))
            budget = budget_total
            actual = budget_total * frac * float(ctx.rng.uniform(0.98, 1.01))
            # Healthy baseline: forecast tracks budget almost exactly (overrun ~ 0), so the
            # injected Falcon overrun is the only material cost-exposure driver.
            forecast = budget_total * float(ctx.rng.uniform(0.998, 1.002))
            cost_to_complete = max(forecast - actual, 0.0)
            # Earned value tracks actual on healthy projects.
            earned_value = actual * float(ctx.rng.uniform(0.99, 1.01))
            rows.append({
                "project_id": w["project_id"],
                "wbs_id": w["wbs_id"],
                "period": period,
                "budget": money(budget),
                "actual_cost": money(actual),
                "forecast_cost": money(forecast),
                "cost_to_complete": money(cost_to_complete),
                "earned_value": money(earned_value),
                "origin_system": "SAP",
            })

    ctx.add("sap_fi_cost", pd.DataFrame(rows))
