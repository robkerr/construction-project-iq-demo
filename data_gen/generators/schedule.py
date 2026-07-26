"""Schedule activities: fact_schedule_activity.

Origin system (narrative): non-SAP — Primavera P6 export. This is the analytical spine.
Baseline is healthy (forecast == baseline for most activities, positive float). The
Falcon slip + negative critical-path float is injected later in seed_scenario.py.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .common import GenContext, iso

_ACTIVITY_VERBS = {
    "Civil": ["Excavation", "Foundations", "Grading", "Underground utilities", "Paving"],
    "Mechanical": ["Equipment set", "Alignment", "Rotating equipment install", "Package tie-in"],
    "Electrical": ["Cable pulling", "Terminations", "Switchgear install", "Lighting install"],
    "Piping": ["Spool fabrication", "Pipe erection", "Hydrotest", "Small-bore install"],
    "I&C": ["Instrument install", "Loop checks", "Control system config", "Calibration"],
    "Structural": ["Steel erection", "Deck install", "Bolt-up", "Grouting"],
    "Process": ["System flush", "Pre-commissioning", "Commissioning", "Performance test"],
}


def generate(ctx: GenContext) -> None:
    wbs = ctx.get("dim_wbs")
    projects = ctx.get("dim_project").set_index("project_id")
    today = ctx.today
    lo = int(ctx.config["activities_per_wbs_min"])
    hi = int(ctx.config["activities_per_wbs_max"])
    slip_rate = float(ctx.config["baseline_minor_slip_rate"])
    max_minor = int(ctx.config["baseline_max_minor_slip_days"])

    rows = []
    counter = 1
    for _, w in wbs.iterrows():
        pid = w["project_id"]
        disc = w["discipline"]
        proj_start = pd.to_datetime(projects.loc[pid, "start_date"]).date()
        proj_finish = pd.to_datetime(projects.loc[pid, "planned_finish"]).date()
        span = max((proj_finish - proj_start).days, 60)
        verbs = _ACTIVITY_VERBS.get(disc, ["Install", "Test"])

        k = int(ctx.rng.integers(lo, hi + 1))
        for _ in range(k):
            baseline_start = proj_start + timedelta(days=int(ctx.rng.integers(0, span)))
            duration = int(ctx.rng.integers(10, 120))
            baseline_finish = baseline_start + timedelta(days=duration)
            is_cp = bool(ctx.rng.random() < 0.12)

            # Healthy baseline: forecast == baseline. Only NON critical-path activities are
            # allowed a small benign slip, so baseline "critical path at risk" is exactly 0
            # and the injected Falcon story is the only source of critical-path risk.
            slip = 0
            if not is_cp and ctx.rng.random() < slip_rate:
                slip = int(ctx.rng.integers(1, max_minor + 1))
            forecast_finish = baseline_finish + timedelta(days=slip)

            # Float: positive slack in the baseline; critical-path activities run tighter but
            # never negative in the baseline.
            if is_cp:
                total_float = int(ctx.rng.integers(0, 8))
            else:
                total_float = int(ctx.rng.integers(5, 60)) - slip

            # Completed if the (forecast) finish is already in the past.
            if forecast_finish <= today:
                actual_finish = forecast_finish
            else:
                actual_finish = None

            rows.append({
                "activity_id": f"ACT-{counter:06d}",
                "wbs_id": w["wbs_id"],
                "project_id": pid,
                "activity_name": f"{ctx.rng.choice(verbs)} - {w['wbs_name']}",
                "baseline_start": iso(baseline_start),
                "baseline_finish": iso(baseline_finish),
                "forecast_finish": iso(forecast_finish),
                "actual_finish": iso(actual_finish),
                "total_float_days": int(total_float),
                "is_critical_path": is_cp,
                "origin_system": "non-SAP",
            })
            counter += 1

    ctx.add("fact_schedule_activity", pd.DataFrame(rows))
