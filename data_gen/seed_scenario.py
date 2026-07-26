"""Deterministic "at-risk" injection — the hero story.

Baseline generation leaves every project healthy. This module injects a schedule-risk
story into Project Falcon (PRJ-001) and two weaker secondaries, such that Falcon is the
unambiguous #1 schedule-risk project and its drivers span BOTH a SAP system (a late
long-lead PO + cost overrun) and a NON-SAP system (a negative-float critical-path slip +
an approved engineering change). That cross-system fusion is the whole point of the demo.

Intensities are ordered Falcon > PRJ-002 > PRJ-003 so the ranking is unambiguous.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from generators.common import GenContext

# Per-project injection intensity (descending, so ranking is unambiguous).
# ec_id is fixed for Falcon (EC-1207) per the build plan; secondaries reuse an existing EC.
INJECTIONS = [
    dict(project_id="PRJ-001", slip_days=28, min_float=-12, n_cp_slip=5,
         po_late_days=25, ec_impact=18, ec_id="EC-1207", overrun_amount=1_000_000,
         n_signals=2),
    dict(project_id="PRJ-002", slip_days=20, min_float=-8, n_cp_slip=3,
         po_late_days=18, ec_impact=12, ec_id=None, overrun_amount=600_000,
         n_signals=1),
    dict(project_id="PRJ-003", slip_days=15, min_float=-5, n_cp_slip=2,
         po_late_days=12, ec_impact=9, ec_id=None, overrun_amount=300_000,
         n_signals=1),
]


def _pick_hero_wbs(ctx: GenContext, project_id: str) -> str:
    """Deterministically pick a WBS on the project that has critical-path activities."""
    acts = ctx.get("fact_schedule_activity")
    cp = acts[(acts["project_id"] == project_id) & (acts["is_critical_path"])]
    if len(cp) == 0:
        cp = acts[acts["project_id"] == project_id]
    return sorted(cp["wbs_id"].unique())[0]


def _ensure_high_risk_supplier(ctx: GenContext) -> str:
    sup = ctx.get("sap_supplier")
    high = sup[sup["risk_rating"] == "High"]
    if len(high) == 0:
        sup.loc[sup.index[0], "risk_rating"] = "High"
        return sup.loc[sup.index[0], "supplier_id"]
    return sorted(high["supplier_id"].tolist())[0]


def apply(ctx: GenContext) -> list[dict]:
    proj = ctx.get("dim_project")
    acts = ctx.get("fact_schedule_activity")
    ecs = ctx.get("fact_engineering_change")
    pos = ctx.get("sap_mm_po")
    cost = ctx.get("sap_fi_cost")
    signals = ctx.get("ext_disruption_signal")
    today = ctx.today

    high_supplier = _ensure_high_risk_supplier(ctx)
    new_signals = []
    summary = []

    for inj in INJECTIONS:
        pid = inj["project_id"]
        hero_wbs = _pick_hero_wbs(ctx, pid)

        # ---- 1. NON-SAP: slip N critical-path activities on the hero WBS ----
        cp_mask = (acts["project_id"] == pid) & (acts["wbs_id"] == hero_wbs) & (acts["is_critical_path"])
        cp_idx = list(acts[cp_mask].index)
        if len(cp_idx) < inj["n_cp_slip"]:
            # widen to any critical-path activity on the project
            cp_idx = list(acts[(acts["project_id"] == pid) & (acts["is_critical_path"])].index)
        cp_idx = sorted(cp_idx)[: inj["n_cp_slip"]]

        for rank, ridx in enumerate(cp_idx):
            # Worst activity gets the full slip / most-negative float; others scale down.
            frac = 1.0 - (rank / max(len(cp_idx), 1)) * 0.5
            slip = max(int(round(inj["slip_days"] * frac)), 3)
            fl = int(round(inj["min_float"] * frac))
            bfin = pd.to_datetime(acts.at[ridx, "baseline_finish"]).date()
            acts.at[ridx, "forecast_finish"] = (bfin + timedelta(days=slip)).isoformat()
            acts.at[ridx, "total_float_days"] = fl
            acts.at[ridx, "actual_finish"] = None  # in progress / not yet finished

        affected_activity = acts.at[cp_idx[0], "activity_id"]
        worst_slip = inj["slip_days"]

        # ---- 1b. Slip the project-level forecast finish past planned finish ----
        prow = proj[proj["project_id"] == pid].index[0]
        planned = pd.to_datetime(proj.at[prow, "planned_finish"]).date()
        proj.at[prow, "forecast_finish"] = (planned + timedelta(days=worst_slip)).isoformat()

        # ---- 2. NON-SAP: approved engineering change on the hero WBS ----
        if inj["ec_id"]:
            # Repurpose the fixed EC id (EC-1207) so the number is stable for the demo.
            ec_mask = ecs["ec_id"] == inj["ec_id"]
            if not ec_mask.any():
                # append if that id somehow doesn't exist
                ecs.loc[len(ecs)] = ecs.iloc[0]
                ec_mask = ecs.index == (len(ecs) - 1)
            eidx = ecs[ec_mask].index[0]
        else:
            # reuse an existing EC on the hero WBS (or any EC on the project)
            cand = ecs[(ecs["project_id"] == pid) & (ecs["wbs_id"] == hero_wbs)]
            if len(cand) == 0:
                cand = ecs[ecs["project_id"] == pid]
            eidx = sorted(cand.index)[0]

        ec_disc = ctx.get("dim_wbs").set_index("wbs_id").at[hero_wbs, "discipline"]
        ecs.at[eidx, "project_id"] = pid
        ecs.at[eidx, "wbs_id"] = hero_wbs
        ecs.at[eidx, "discipline"] = ec_disc
        ecs.at[eidx, "title"] = f"Client-requested scope change on {ec_disc} critical path"
        ecs.at[eidx, "status"] = "Approved"
        ecs.at[eidx, "schedule_impact_days"] = inj["ec_impact"]
        ecs.at[eidx, "issued_date"] = (today - timedelta(days=35)).isoformat()
        ecs.at[eidx, "affected_activity_id"] = affected_activity
        injected_ec_id = ecs.at[eidx, "ec_id"]

        # ---- 3. SAP: late long-lead PO on the hero WBS from a High-risk supplier ----
        po_cand = pos[(pos["project_id"] == pid) & (pos["wbs_id"] == hero_wbs)]
        if len(po_cand) == 0:
            po_cand = pos[pos["project_id"] == pid]
        poidx = sorted(po_cand.index)[0]
        pos.at[poidx, "wbs_id"] = hero_wbs
        pos.at[poidx, "is_long_lead"] = True
        if pos.at[poidx, "material_desc"] not in _LONG_LEAD_SET:
            pos.at[poidx, "material_desc"] = "Main power transformer (230kV)"
        promised = pd.to_datetime(pos.at[poidx, "promised_date"]).date()
        pos.at[poidx, "status"] = "Late"
        pos.at[poidx, "revised_date"] = (promised + timedelta(days=inj["po_late_days"])).isoformat()
        pos.at[poidx, "supplier_id"] = high_supplier
        injected_po_id = pos.at[poidx, "po_id"]

        # ---- 4. SAP: cost overrun + cost-to-complete exposure on the hero WBS ----
        cmask = (cost["project_id"] == pid) & (cost["wbs_id"] == hero_wbs)
        cidx = list(cost[cmask].index)
        per_period = inj["overrun_amount"] / max(len(cidx), 1)
        for ridx in cidx:
            cost.at[ridx, "forecast_cost"] = round(cost.at[ridx, "forecast_cost"] + per_period, 2)
            cost.at[ridx, "cost_to_complete"] = round(cost.at[ridx, "cost_to_complete"] + per_period, 2)
            # earned value lags actual (schedule/cost variance)
            cost.at[ridx, "earned_value"] = round(cost.at[ridx, "earned_value"] * 0.88, 2)

        # ---- 5. External corroboration: disruption signal on the supplier ----
        for s in range(inj["n_signals"]):
            new_signals.append({
                "signal_id": f"SIG-9{len(new_signals) + 1:03d}",
                "scope": high_supplier,
                "scope_kind": "supplier",
                "event_type": "Supplier financial distress" if s == 0 else "Port congestion",
                "event_date": (today - timedelta(days=20 + s * 10)).isoformat(),
                "severity": "High",
                "origin_system": "external",
            })

        summary.append({
            "project_id": pid,
            "hero_wbs": hero_wbs,
            "ec_id": injected_ec_id,
            "po_id": injected_po_id,
            "supplier_id": high_supplier,
            "worst_slip_days": worst_slip,
            "min_float": inj["min_float"],
            "overrun_amount": inj["overrun_amount"],
        })

    if new_signals:
        ctx.frames["ext_disruption_signal"] = pd.concat(
            [signals, pd.DataFrame(new_signals)], ignore_index=True)

    return summary


# Set of long-lead material descriptions (import lazily to avoid a circular import at top).
from generators.common import LONG_LEAD_MATERIALS as _LL  # noqa: E402
_LONG_LEAD_SET = set(_LL)
