"""Source 3 - Amazon S3 Parquet: Government permits & inspections (shortcut).

Narrative: an external data provider aggregates public regulatory records
(permits, inspections, code violations, fees, environmental readings) and drops
them as Parquet in an S3 bucket. Fabric surfaces them in the bronze lakehouse via
a OneLake shortcut to the S3 prefix (no data movement).

Six tables (one parquet prefix each):
    authority              (dim)
    permit                 (refs project_id)
    inspection             (refs permit_id/project_id)
    code_violation         (refs project_id/inspection_id)
    permit_fee             (refs permit_id/project_id)
    environmental_reading  (refs project_id)

Project Falcon (PRJ-001) gets a FAILED environmental inspection + an OPEN critical
code violation, reinforcing the schedule-risk story from a third external system.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from .base import (ExtContext, ORIGIN_S3, ids, iso, money, weighted_pick,
                   rand_dates, write_parquet)

SUBDIR = "s3"

PERMIT_TYPES = {"Building": 0.28, "Electrical": 0.2, "Grading": 0.14,
                "Environmental": 0.16, "Air Quality": 0.12, "Occupancy": 0.10}
PERMIT_STATUS = {"Issued": 0.6, "Under Review": 0.15, "Applied": 0.1,
                 "Expired": 0.1, "Denied": 0.05}
INSPECTION_TYPES = ["Foundation", "Framing", "Electrical Rough-In", "Environmental",
                    "Fire & Life Safety", "Air Emissions", "Stormwater", "Final"]
PARAMETERS = [("PM2.5", "ug/m3", 35.0), ("Noise", "dBA", 85.0), ("Turbidity", "NTU", 50.0),
              ("VOC", "ppm", 5.0), ("CO", "ppm", 9.0)]
VIOLATION_SECTIONS = ["IBC 1704", "NEC 250.50", "EPA NPDES-402", "OSHA 1926.501",
                      "IFC 3304", "40 CFR 60", "Local Grading 8.12"]
AUTHORITY_TYPES = ["Building Department", "Environmental Agency", "Fire Marshal",
                   "Air Quality District", "Water Board", "Labor & Safety"]


def _build_authorities(ctx: ExtContext) -> pd.DataFrame:
    """One set of permitting authorities per region present in the portfolio."""
    regions = ctx.projects[["region", "country"]].drop_duplicates().reset_index(drop=True)
    rows = []
    for _, r in regions.iterrows():
        for atype in AUTHORITY_TYPES:
            rows.append({
                "authority_name": f"{r['country']} {atype}",
                "authority_type": atype,
                "jurisdiction": r["country"],
                "region": r["region"],
                "country": r["country"],
            })
    df = pd.DataFrame(rows)
    df.insert(0, "authority_id", ids("AUTH-", len(df), width=4))
    df["origin_system"] = ORIGIN_S3
    return df


def _build_permits(ctx: ExtContext, authorities: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in ctx.projects.iterrows():
        region_auth = authorities[authorities.region == p["region"]]
        n_permits = int(ctx.rng.integers(5, 12))
        for _ in range(n_permits):
            ptype = weighted_pick(ctx, PERMIT_TYPES, 1)[0]
            # pick an authority whose type roughly matches the permit type
            auth = region_auth.sample(n=1, random_state=int(ctx.rng.integers(0, 1_000_000))).iloc[0]
            applied = p["start_date"]
            applied_d = pd.to_datetime(applied).date() + timedelta(days=int(ctx.rng.integers(0, 120)))
            status = weighted_pick(ctx, PERMIT_STATUS, 1)[0]
            issued_d = applied_d + timedelta(days=int(ctx.rng.integers(10, 90))) if status in (
                "Issued", "Expired", "Occupancy") else None
            expiry_d = (issued_d + timedelta(days=365)) if issued_d else None
            rows.append({
                "project_id": p["project_id"],
                "authority_id": auth["authority_id"],
                "permit_type": ptype,
                "applied_date": iso(applied_d),
                "issued_date": iso(issued_d),
                "expiry_date": iso(expiry_d),
                "status": status,
                "valuation_usd": money(ctx.rng.uniform(50_000, 8_000_000))[()],
            })
    df = pd.DataFrame(rows)
    df.insert(0, "permit_id", ids("PMT-", len(df), width=6))
    df["origin_system"] = ORIGIN_S3
    return df


def _build_inspections(ctx: ExtContext, permits: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, pm in permits.iterrows():
        if pm["status"] not in ("Issued", "Expired", "Under Review"):
            continue
        n_insp = int(ctx.rng.integers(1, 5))
        base = pd.to_datetime(pm["issued_date"] or pm["applied_date"]).date()
        for _ in range(n_insp):
            sched = base + timedelta(days=int(ctx.rng.integers(5, 200)))
            done = ctx.rng.random() < 0.85
            rows.append({
                "permit_id": pm["permit_id"],
                "project_id": pm["project_id"],
                "inspection_type": ctx.rng.choice(INSPECTION_TYPES),
                "scheduled_date": iso(sched),
                "inspection_date": iso(sched + timedelta(days=int(ctx.rng.integers(0, 5)))) if done else None,
                "inspector_name": ctx.faker.name(),
                "result": weighted_pick(ctx, {"Pass": 0.72, "Partial": 0.14, "Fail": 0.14}, 1)[0]
                if done else "Pending",
            })
    df = pd.DataFrame(rows)
    df.insert(0, "inspection_id", ids("INS-", len(df), width=6))
    df["origin_system"] = ORIGIN_S3
    return df


def _build_violations(ctx: ExtContext, inspections: pd.DataFrame) -> pd.DataFrame:
    failed = inspections[inspections.result.isin(["Fail", "Partial"])]
    rows = []
    for _, ins in failed.iterrows():
        if ctx.rng.random() > 0.75:
            continue
        issued = pd.to_datetime(ins["inspection_date"] or ins["scheduled_date"]).date()
        sev = weighted_pick(ctx, {"Minor": 0.5, "Major": 0.35, "Critical": 0.15}, 1)[0]
        resolved = ctx.rng.random() < 0.6
        rows.append({
            "project_id": ins["project_id"],
            "inspection_id": ins["inspection_id"],
            "code_section": ctx.rng.choice(VIOLATION_SECTIONS),
            "severity": sev,
            "description": ctx.faker.sentence(nb_words=8).rstrip("."),
            "issued_date": iso(issued),
            "resolved_date": iso(issued + timedelta(days=int(ctx.rng.integers(5, 90)))) if resolved else None,
            "status": "Resolved" if resolved else "Open",
        })
    df = pd.DataFrame(rows)
    df.insert(0, "violation_id", ids("VIO-", len(df), width=6))
    df["origin_system"] = ORIGIN_S3
    return df


def _build_fees(ctx: ExtContext, permits: pd.DataFrame) -> pd.DataFrame:
    fee_types = ["Application Fee", "Plan Review", "Inspection Fee", "Impact Fee", "Renewal Fee"]
    rows = []
    for _, pm in permits.iterrows():
        for _ in range(int(ctx.rng.integers(1, 4))):
            paid = ctx.rng.random() < 0.75
            invoice = pd.to_datetime(pm["applied_date"]).date() + timedelta(days=int(ctx.rng.integers(0, 60)))
            rows.append({
                "permit_id": pm["permit_id"],
                "project_id": pm["project_id"],
                "fee_type": ctx.rng.choice(fee_types),
                "amount_usd": money(ctx.rng.uniform(500, 120_000))[()],
                "invoice_date": iso(invoice),
                "paid_date": iso(invoice + timedelta(days=int(ctx.rng.integers(5, 45)))) if paid else None,
                "status": "Paid" if paid else "Outstanding",
            })
    df = pd.DataFrame(rows)
    df.insert(0, "fee_id", ids("FEE-", len(df), width=6))
    df["origin_system"] = ORIGIN_S3
    return df


def _build_environmental(ctx: ExtContext) -> pd.DataFrame:
    rows = []
    for _, p in ctx.projects.iterrows():
        n_stations = int(ctx.rng.integers(1, 4))
        for s in range(n_stations):
            station = f"{p['project_id']}-ENV-{s + 1:02d}"
            # weekly readings over the last ~20 weeks
            for wk in range(20):
                param, unit, limit = PARAMETERS[int(ctx.rng.integers(0, len(PARAMETERS)))]
                read_date = ctx.today - timedelta(weeks=wk)
                value = round(float(ctx.rng.uniform(0.2, 1.05)) * limit, 2)
                rows.append({
                    "project_id": p["project_id"],
                    "station_id": station,
                    "reading_date": iso(read_date),
                    "parameter": param,
                    "value": value,
                    "unit": unit,
                    "permit_limit": limit,
                    "exceedance_flag": bool(value > limit),
                })
    df = pd.DataFrame(rows)
    df.insert(0, "reading_id", ids("ENV-", len(df), width=7))
    df["origin_system"] = ORIGIN_S3
    return df


def _inject_falcon(ctx, permits, inspections, violations, environmental):
    """Falcon (PRJ-001): failed environmental inspection + open critical violation + exceedances."""
    # Ensure Falcon has an Environmental permit to hang the inspection on.
    falcon_env = permits[(permits.project_id == "PRJ-001") & (permits.permit_type == "Environmental")]
    if falcon_env.empty:
        falcon_env = permits[permits.project_id == "PRJ-001"]
    permit_id = falcon_env.iloc[0]["permit_id"] if not falcon_env.empty else "PMT-000001"

    ins_id = "INS-900001"
    fail_ins = {
        "inspection_id": ins_id, "permit_id": permit_id, "project_id": "PRJ-001",
        "inspection_type": "Environmental",
        "scheduled_date": iso(ctx.today - timedelta(days=21)),
        "inspection_date": iso(ctx.today - timedelta(days=20)),
        "inspector_name": ctx.faker.name(), "result": "Fail", "origin_system": ORIGIN_S3,
    }
    inspections = pd.concat([pd.DataFrame([fail_ins]), inspections], ignore_index=True)

    vio = {
        "violation_id": "VIO-900001", "project_id": "PRJ-001", "inspection_id": ins_id,
        "code_section": "EPA NPDES-402", "severity": "Critical",
        "description": "Stormwater discharge exceeded permitted turbidity limit during transformer pad works",
        "issued_date": iso(ctx.today - timedelta(days=20)), "resolved_date": None,
        "status": "Open", "origin_system": ORIGIN_S3,
    }
    violations = pd.concat([pd.DataFrame([vio]), violations], ignore_index=True)

    # A couple of turbidity exceedances on Falcon's environmental station.
    ex_rows = []
    for wk in range(3):
        ex_rows.append({
            "reading_id": f"ENV-990000{wk + 1}", "project_id": "PRJ-001",
            "station_id": "PRJ-001-ENV-01", "reading_date": iso(ctx.today - timedelta(weeks=wk, days=1)),
            "parameter": "Turbidity", "value": round(float(ctx.rng.uniform(55, 80)), 2),
            "unit": "NTU", "permit_limit": 50.0, "exceedance_flag": True, "origin_system": ORIGIN_S3,
        })
    environmental = pd.concat([pd.DataFrame(ex_rows), environmental], ignore_index=True)
    return inspections, violations, environmental


def generate(ctx: ExtContext) -> dict:
    authorities = _build_authorities(ctx)
    permits = _build_permits(ctx, authorities)
    inspections = _build_inspections(ctx, permits)
    violations = _build_violations(ctx, inspections)
    fees = _build_fees(ctx, permits)
    environmental = _build_environmental(ctx)
    inspections, violations, environmental = _inject_falcon(
        ctx, permits, inspections, violations, environmental)

    tables = {
        "authority": authorities,
        "permit": permits,
        "inspection": inspections,
        "code_violation": violations,
        "permit_fee": fees,
        "environmental_reading": environmental,
    }
    for name, df in tables.items():
        write_parquet(df, SUBDIR + "/permits", name)
    return tables
