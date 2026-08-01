"""Source 1 - Google BigQuery: Work Order Management (mirrored into Fabric).

Narrative: a Maximo-style maintenance/work-management system running in Google
Cloud. Mirrored into Fabric OneLake, then surfaced in the bronze lakehouse via a
shortcut to the mirrored tables.

Six tables:
    equipment_asset            (dim)  - asset registry incl. hero tag ET-1001
    work_order                 (fact) - WO headers
    work_order_task            (fact) - WO task lines
    work_order_labor           (fact) - labor postings
    work_order_material        (fact) - material usage (refs supplier_id)
    work_order_status_history  (fact) - status transitions

All rows carry origin_system = 'GCP-BigQuery' and reference real project_id /
wbs_id / equipment_tag / supplier_id keys from the core model.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .base import (ExtContext, ORIGIN_BIGQUERY, CRAFTS, ids, iso, money,
                   weighted_pick, asset_class_for, write_parquet, write_csv)

SUBDIR = "bigquery"

WO_TYPES = {"Preventive": 0.42, "Corrective": 0.33, "Inspection": 0.15, "Emergency": 0.10}
WO_STATUS = {"Completed": 0.55, "In Progress": 0.18, "Open": 0.15, "On Hold": 0.07, "Cancelled": 0.05}
PRIORITY = {"Low": 0.30, "Medium": 0.40, "High": 0.22, "Critical": 0.08}
MANUFACTURERS = ["Siemens", "ABB", "GE Vernova", "Flowserve", "Sulzer", "Alfa Laval",
                 "Emerson", "Schneider Electric", "Baker Hughes", "Atlas Copco"]
MATERIAL_ITEMS = ["Bearing set", "Gasket kit", "Seal assembly", "Control card",
                  "Lubricant drum", "Filter element", "Valve actuator", "Coupling",
                  "Motor winding kit", "Pressure transmitter", "Relay module", "Impeller"]


def _build_assets(ctx: ExtContext) -> pd.DataFrame:
    """Asset registry: seed with the real RFQ equipment tags, then add more per project."""
    rows = []
    seen = set()

    # 1) Real engineered-equipment tags from the core model (includes ET-1001).
    for _, r in ctx.rfq.iterrows():
        tag = r["equipment_tag"]
        if tag in seen:
            continue
        seen.add(tag)
        rows.append({
            "equipment_tag": tag,
            "project_id": r["project_id"],
            "wbs_id": r["wbs_id"],
            "asset_class": asset_class_for(tag),
        })

    # 2) Additional operating assets per project so the registry looks realistic.
    projects = ctx.projects["project_id"].tolist()
    wbs_by_proj = {p: ctx.wbs[ctx.wbs.project_id == p]["wbs_id"].tolist() for p in projects}
    extra_counter = {"ET": 2000, "HX": 2000, "P": 2000, "TK": 3000, "CV": 4000}
    for p in projects:
        n_extra = int(ctx.rng.integers(4, 9))
        for _ in range(n_extra):
            prefix = ctx.rng.choice(list(extra_counter.keys()))
            extra_counter[prefix] += 1
            tag = f"{prefix}-{extra_counter[prefix]}"
            if tag in seen:
                continue
            seen.add(tag)
            wlist = wbs_by_proj.get(p) or [None]
            rows.append({
                "equipment_tag": tag,
                "project_id": p,
                "wbs_id": ctx.rng.choice(wlist) if wlist and wlist[0] else None,
                "asset_class": asset_class_for(tag) if prefix in ("ET", "HX", "P")
                else {"TK": "Storage Tank", "CV": "Control Valve"}[prefix],
            })

    df = pd.DataFrame(rows).reset_index(drop=True)
    df.insert(0, "asset_id", ids("AST-", len(df), width=5))
    n = len(df)
    df["manufacturer"] = ctx.rng.choice(MANUFACTURERS, size=n)
    df["model_no"] = ["MDL-" + "".join(ctx.rng.choice(list("ABCDEFGHJKLMNPQRSTUVWXYZ23456789"), size=6))
                      for _ in range(n)]
    df["criticality"] = weighted_pick(ctx, {"A": 0.2, "B": 0.5, "C": 0.3}, n)
    df["install_date"] = [iso(d) for d in
                          [ctx.today - timedelta(days=int(x)) for x in ctx.rng.integers(200, 1400, n)]]
    df["operational_status"] = weighted_pick(
        ctx, {"In Service": 0.82, "Standby": 0.1, "Out of Service": 0.05, "Decommissioned": 0.03}, n)
    df["origin_system"] = ORIGIN_BIGQUERY
    return df


def _build_work_orders(ctx: ExtContext, assets: pd.DataFrame) -> pd.DataFrame:
    n = 820
    asset_rows = assets.sample(n=n, replace=True, random_state=ctx.rng.integers(0, 1_000_000)).reset_index(drop=True)
    wo = pd.DataFrame({
        "wo_id": ids("WO-", n, width=6),
        "equipment_tag": asset_rows["equipment_tag"].values,
        "project_id": asset_rows["project_id"].values,
        "wbs_id": asset_rows["wbs_id"].values,
        "asset_id": asset_rows["asset_id"].values,
    })
    wo["wo_type"] = weighted_pick(ctx, WO_TYPES, n)
    wo["priority"] = weighted_pick(ctx, PRIORITY, n)
    wo["status"] = weighted_pick(ctx, WO_STATUS, n)

    reported = [ctx.today - timedelta(days=int(x)) for x in ctx.rng.integers(1, 540, n)]
    wo["reported_date"] = [iso(d) for d in reported]
    sched = [rd + timedelta(days=int(x)) for rd, x in zip(reported, ctx.rng.integers(1, 21, n))]
    wo["scheduled_date"] = [iso(d) for d in sched]
    completed = []
    for st, sd in zip(wo["status"], sched):
        if st in ("Completed",):
            completed.append(iso(sd + timedelta(days=int(ctx.rng.integers(0, 14)))))
        else:
            completed.append(None)
    wo["completed_date"] = completed
    wo["reported_by"] = [ctx.faker.name() for _ in range(n)]
    wo["estimated_hours"] = money(ctx.rng.uniform(4, 160, n))
    wo["actual_hours"] = [money(eh * float(ctx.rng.uniform(0.7, 1.6)))[()] if st == "Completed" else None
                          for eh, st in zip(wo["estimated_hours"], wo["status"])]
    wo["origin_system"] = ORIGIN_BIGQUERY
    return wo


def _inject_falcon(ctx: ExtContext, assets: pd.DataFrame, wo: pd.DataFrame) -> pd.DataFrame:
    """Hero tie-in: an emergency corrective WO on ET-1001 (Project Falcon transformer)."""
    et = assets[assets.equipment_tag == "ET-1001"]
    if et.empty:
        return wo
    a = et.iloc[0]
    falcon = {
        "wo_id": "WO-900001",
        "equipment_tag": "ET-1001",
        "project_id": a["project_id"],
        "wbs_id": a["wbs_id"],
        "asset_id": a["asset_id"],
        "wo_type": "Emergency",
        "priority": "Critical",
        "status": "In Progress",
        "reported_date": iso(ctx.today - timedelta(days=9)),
        "scheduled_date": iso(ctx.today - timedelta(days=7)),
        "completed_date": None,
        "reported_by": ctx.faker.name(),
        "estimated_hours": 240.0,
        "actual_hours": None,
        "origin_system": ORIGIN_BIGQUERY,
    }
    return pd.concat([pd.DataFrame([falcon]), wo], ignore_index=True)


def _build_tasks(ctx: ExtContext, wo: pd.DataFrame) -> pd.DataFrame:
    rows = []
    disciplines = ["Mechanical", "Electrical", "I&C", "Piping", "Structural"]
    for _, w in wo.iterrows():
        n_tasks = int(ctx.rng.integers(1, 5))
        for seq in range(1, n_tasks + 1):
            planned = float(ctx.rng.uniform(2, 40))
            done = w["status"] == "Completed"
            rows.append({
                "wo_id": w["wo_id"],
                "task_seq": seq,
                "discipline": ctx.rng.choice(disciplines),
                "description": ctx.faker.sentence(nb_words=6).rstrip("."),
                "task_status": "Completed" if done else ctx.rng.choice(["Open", "In Progress", "Completed"]),
                "planned_hours": round(planned, 2),
                "actual_hours": round(planned * float(ctx.rng.uniform(0.7, 1.5)), 2) if done else None,
            })
    df = pd.DataFrame(rows)
    df.insert(0, "task_id", ids("WOT-", len(df), width=7))
    df["origin_system"] = ORIGIN_BIGQUERY
    return df


def _build_labor(ctx: ExtContext, wo: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, w in wo.iterrows():
        if w["status"] not in ("Completed", "In Progress"):
            continue
        n_post = int(ctx.rng.integers(1, 5))
        for _ in range(n_post):
            hrs = round(float(ctx.rng.uniform(2, 12)), 2)
            rate = round(float(ctx.rng.uniform(48, 135)), 2)
            rows.append({
                "wo_id": w["wo_id"],
                "project_id": w["project_id"],
                "craft": ctx.rng.choice(CRAFTS),
                "worker_ref": "WKR-" + str(int(ctx.rng.integers(1000, 9999))),
                "hours": hrs,
                "hourly_rate": rate,
                "labor_cost": round(hrs * rate, 2),
                "post_date": w["scheduled_date"],
            })
    df = pd.DataFrame(rows)
    df.insert(0, "labor_id", ids("WOL-", len(df), width=7))
    df["origin_system"] = ORIGIN_BIGQUERY
    return df


def _build_material(ctx: ExtContext, wo: pd.DataFrame) -> pd.DataFrame:
    supplier_ids = ctx.suppliers["supplier_id"].tolist()
    rows = []
    for _, w in wo.iterrows():
        if w["wo_type"] not in ("Corrective", "Emergency"):
            continue
        if ctx.rng.random() > 0.7:
            continue
        n_mat = int(ctx.rng.integers(1, 4))
        for _ in range(n_mat):
            qty = int(ctx.rng.integers(1, 20))
            unit = round(float(ctx.rng.uniform(25, 4200)), 2)
            rows.append({
                "wo_id": w["wo_id"],
                "supplier_id": ctx.rng.choice(supplier_ids),
                "material_desc": ctx.rng.choice(MATERIAL_ITEMS),
                "quantity": qty,
                "unit_cost": unit,
                "total_cost": round(qty * unit, 2),
            })
    df = pd.DataFrame(rows)
    df.insert(0, "wo_material_id", ids("WOM-", len(df), width=7))
    df["origin_system"] = ORIGIN_BIGQUERY
    return df


def _build_status_history(ctx: ExtContext, wo: pd.DataFrame) -> pd.DataFrame:
    flow = ["Open", "In Progress", "On Hold", "Completed", "Cancelled"]
    rows = []
    for _, w in wo.iterrows():
        target = w["status"]
        path = ["Open"]
        if target == "Completed":
            path = ["Open", "In Progress", "Completed"]
        elif target == "In Progress":
            path = ["Open", "In Progress"]
        elif target == "On Hold":
            path = ["Open", "In Progress", "On Hold"]
        elif target == "Cancelled":
            path = ["Open", "Cancelled"]
        base = pd.to_datetime(w["reported_date"]).date()
        for i in range(1, len(path)):
            changed = base + timedelta(days=int(ctx.rng.integers(1, 10)) * i)
            rows.append({
                "wo_id": w["wo_id"],
                "seq": i,
                "from_status": path[i - 1],
                "to_status": path[i],
                "changed_date": iso(changed),
                "changed_by": ctx.faker.name(),
            })
    df = pd.DataFrame(rows)
    df.insert(0, "status_event_id", ids("WOS-", len(df), width=7))
    df["origin_system"] = ORIGIN_BIGQUERY
    return df


def generate(ctx: ExtContext) -> dict:
    assets = _build_assets(ctx)
    wo = _build_work_orders(ctx, assets)
    wo = _inject_falcon(ctx, assets, wo)
    tasks = _build_tasks(ctx, wo)
    labor = _build_labor(ctx, wo)
    material = _build_material(ctx, wo)
    history = _build_status_history(ctx, wo)

    tables = {
        "equipment_asset": assets,
        "work_order": wo,
        "work_order_task": tasks,
        "work_order_labor": labor,
        "work_order_material": material,
        "work_order_status_history": history,
    }
    for name, df in tables.items():
        write_parquet(df, SUBDIR, name)
        write_csv(df, SUBDIR, name)
    return tables
