"""Source 2 - on-prem SQL Server: Time Clock / Labor (mirrored into Fabric).

Narrative: an on-prem time-and-attendance system. Employees clock in/out daily
and charge time to projects and cost codes. Mirrored into Fabric OneLake, then
surfaced in the bronze lakehouse via a shortcut to the mirrored tables.

Six tables (SQL schema [timeclock]):
    employee     (dim)
    crew         (dim)
    cost_code    (dim)
    timesheet    (fact - weekly header)
    time_entry   (fact - daily punch, refs project_id/wbs_id)
    labor_charge (fact - charge to project/cost code)

Emits CSV extracts + schema.sql (DDL, with PKs required for Fabric mirroring) +
load_bulk.sql (BULK INSERT script). Project Falcon (PRJ-001) shows an overtime
crunch consistent with its at-risk story.
"""
from __future__ import annotations

from datetime import timedelta, datetime, time

import numpy as np
import pandas as pd

from .base import (ExtContext, ORIGIN_SQLSERVER, CRAFTS, LABOR_CLASSES,
                   ids, iso, money, weighted_pick, write_csv, OUT_ROOT)

SUBDIR = "sqlserver"
SCHEMA = "timeclock"

N_EMPLOYEES = 120
N_WEEKS = 16  # trailing weeks of timekeeping up to 'today'

# SQL Server DDL: column -> type. Order matters (matches DataFrame column order).
DDL = {
    "employee": [
        ("emp_id", "VARCHAR(12) NOT NULL"),
        ("full_name", "NVARCHAR(120) NOT NULL"),
        ("craft", "VARCHAR(40) NULL"),
        ("labor_class", "VARCHAR(30) NULL"),
        ("region", "VARCHAR(40) NULL"),
        ("hire_date", "DATE NULL"),
        ("hourly_rate", "DECIMAL(9,2) NULL"),
        ("is_active", "BIT NULL"),
        ("origin_system", "VARCHAR(30) NULL"),
    ],
    "crew": [
        ("crew_id", "VARCHAR(12) NOT NULL"),
        ("crew_name", "NVARCHAR(80) NOT NULL"),
        ("foreman_emp_id", "VARCHAR(12) NULL"),
        ("project_id", "VARCHAR(12) NULL"),
        ("discipline", "VARCHAR(30) NULL"),
        ("origin_system", "VARCHAR(30) NULL"),
    ],
    "cost_code": [
        ("cost_code_id", "VARCHAR(16) NOT NULL"),
        ("project_id", "VARCHAR(12) NULL"),
        ("code", "VARCHAR(20) NULL"),
        ("description", "NVARCHAR(120) NULL"),
        ("discipline", "VARCHAR(30) NULL"),
        ("origin_system", "VARCHAR(30) NULL"),
    ],
    "timesheet": [
        ("timesheet_id", "VARCHAR(16) NOT NULL"),
        ("emp_id", "VARCHAR(12) NULL"),
        ("week_ending", "DATE NULL"),
        ("project_id", "VARCHAR(12) NULL"),
        ("status", "VARCHAR(20) NULL"),
        ("total_hours", "DECIMAL(6,2) NULL"),
        ("origin_system", "VARCHAR(30) NULL"),
    ],
    "time_entry": [
        ("entry_id", "VARCHAR(18) NOT NULL"),
        ("timesheet_id", "VARCHAR(16) NULL"),
        ("emp_id", "VARCHAR(12) NULL"),
        ("work_date", "DATE NULL"),
        ("project_id", "VARCHAR(12) NULL"),
        ("wbs_id", "VARCHAR(16) NULL"),
        ("cost_code_id", "VARCHAR(16) NULL"),
        ("clock_in", "DATETIME2(0) NULL"),
        ("clock_out", "DATETIME2(0) NULL"),
        ("hours", "DECIMAL(5,2) NULL"),
        ("overtime_hours", "DECIMAL(5,2) NULL"),
        ("origin_system", "VARCHAR(30) NULL"),
    ],
    "labor_charge": [
        ("charge_id", "VARCHAR(18) NOT NULL"),
        ("project_id", "VARCHAR(12) NULL"),
        ("wbs_id", "VARCHAR(16) NULL"),
        ("cost_code_id", "VARCHAR(16) NULL"),
        ("week_ending", "DATE NULL"),
        ("reg_hours", "DECIMAL(8,2) NULL"),
        ("ot_hours", "DECIMAL(8,2) NULL"),
        ("amount", "DECIMAL(12,2) NULL"),
        ("origin_system", "VARCHAR(30) NULL"),
    ],
}
PRIMARY_KEYS = {
    "employee": "emp_id", "crew": "crew_id", "cost_code": "cost_code_id",
    "timesheet": "timesheet_id", "time_entry": "entry_id", "labor_charge": "charge_id",
}


def _week_endings(ctx: ExtContext) -> list:
    """Trailing Fridays up to the most recent Friday on/before today."""
    d = ctx.today
    while d.weekday() != 4:  # 4 = Friday
        d -= timedelta(days=1)
    return sorted(d - timedelta(weeks=w) for w in range(N_WEEKS))


def _build_employees(ctx: ExtContext) -> pd.DataFrame:
    n = N_EMPLOYEES
    regions = ctx.projects["region"].unique().tolist()
    df = pd.DataFrame({
        "emp_id": ids("EMP-", n, width=4),
        "full_name": [ctx.faker.name() for _ in range(n)],
        "craft": ctx.rng.choice(CRAFTS, size=n),
        "labor_class": weighted_pick(
            ctx, {"Apprentice": 0.25, "Journeyman": 0.45, "Foreman": 0.18,
                  "General Foreman": 0.08, "Superintendent": 0.04}, n),
        "region": ctx.rng.choice(regions, size=n),
    })
    df["hire_date"] = [iso(ctx.today - timedelta(days=int(x))) for x in ctx.rng.integers(120, 3600, n)]
    base_rate = {"Apprentice": 32, "Journeyman": 52, "Foreman": 68,
                 "General Foreman": 82, "Superintendent": 98}
    df["hourly_rate"] = [round(base_rate[lc] * float(ctx.rng.uniform(0.9, 1.15)), 2)
                         for lc in df["labor_class"]]
    df["is_active"] = weighted_pick(ctx, {1: 0.9, 0: 0.1}, n)
    df["origin_system"] = ORIGIN_SQLSERVER
    return df


def _build_crews(ctx: ExtContext, employees: pd.DataFrame) -> pd.DataFrame:
    projects = ctx.projects["project_id"].tolist()
    disciplines = ctx.wbs["discipline"].unique().tolist()
    foremen = employees[employees.labor_class.isin(["Foreman", "General Foreman"])]["emp_id"].tolist()
    rows = []
    for p in projects:
        for _ in range(int(ctx.rng.integers(2, 5))):
            rows.append({
                "crew_name": f"{ctx.rng.choice(disciplines)} Crew {int(ctx.rng.integers(1, 30))}",
                "foreman_emp_id": ctx.rng.choice(foremen) if foremen else None,
                "project_id": p,
                "discipline": ctx.rng.choice(disciplines),
            })
    df = pd.DataFrame(rows)
    df.insert(0, "crew_id", ids("CRW-", len(df), width=4))
    df["origin_system"] = ORIGIN_SQLSERVER
    return df


def _build_cost_codes(ctx: ExtContext) -> pd.DataFrame:
    rows = []
    templ = [("01", "Site Preparation"), ("02", "Concrete"), ("03", "Structural Steel"),
             ("04", "Mechanical Equipment"), ("05", "Piping"), ("06", "Electrical"),
             ("07", "Instrumentation"), ("08", "Insulation & Coatings"), ("09", "Commissioning")]
    for p in ctx.projects["project_id"].tolist():
        disc_map = ctx.wbs[ctx.wbs.project_id == p]["discipline"].tolist() or ["Civil"]
        for code, desc in templ:
            rows.append({
                "project_id": p,
                "code": f"{p.split('-')[1]}-{code}",
                "description": desc,
                "discipline": ctx.rng.choice(disc_map),
            })
    df = pd.DataFrame(rows)
    df.insert(0, "cost_code_id", ids("CC-", len(df), width=5))
    df["origin_system"] = ORIGIN_SQLSERVER
    return df


def _build_timesheets_entries(ctx: ExtContext, employees, cost_codes):
    weeks = _week_endings(ctx)
    proj_wbs = {p: ctx.wbs[ctx.wbs.project_id == p]["wbs_id"].tolist()
                for p in ctx.projects["project_id"].tolist()}
    proj_cc = {p: cost_codes[cost_codes.project_id == p]["cost_code_id"].tolist()
               for p in ctx.projects["project_id"].tolist()}
    projects = ctx.projects["project_id"].tolist()

    # Assign each active employee a "home" project for the period.
    active = employees[employees.is_active == 1].reset_index(drop=True)
    emp_home = {r.emp_id: ctx.rng.choice(projects) for r in active.itertuples()}

    ts_rows, te_rows = [], []
    ts_counter, te_counter = 0, 0
    for r in active.itertuples():
        home = emp_home[r.emp_id]
        # each employee works ~ a random contiguous subset of the weeks
        first_wk = int(ctx.rng.integers(0, max(1, len(weeks) - 6)))
        for wk in weeks[first_wk:]:
            if ctx.rng.random() < 0.08:  # occasional missed week
                continue
            proj = home if ctx.rng.random() < 0.85 else ctx.rng.choice(projects)
            ts_counter += 1
            ts_id = f"TS-{ts_counter:07d}"
            # Falcon overtime crunch: heavier days near deadline.
            is_falcon = proj == "PRJ-001"
            days = 5 + (1 if (is_falcon and ctx.rng.random() < 0.6) else 0)  # Sat OT on Falcon
            total = 0.0
            for dnum in range(days):
                work_date = wk - timedelta(days=(4 - dnum) if dnum < 5 else -1)
                base_hours = 8.0
                ot = 0.0
                if is_falcon and ctx.rng.random() < 0.5:
                    ot = round(float(ctx.rng.uniform(1, 4)), 2)
                elif ctx.rng.random() < 0.15:
                    ot = round(float(ctx.rng.uniform(0.5, 2)), 2)
                if dnum == 5:  # Saturday overtime day
                    base_hours = 0.0
                    ot = round(float(ctx.rng.uniform(6, 10)), 2)
                hrs = round(base_hours + ot, 2)
                if hrs <= 0:
                    continue
                start_hour = 6 if not is_falcon else int(ctx.rng.choice([6, 7]))
                clock_in = datetime.combine(work_date, time(start_hour, int(ctx.rng.choice([0, 15, 30]))))
                clock_out = clock_in + timedelta(hours=hrs + 0.5)  # +0.5 unpaid lunch
                wlist = proj_wbs.get(proj) or [None]
                cclist = proj_cc.get(proj) or [None]
                te_counter += 1
                te_rows.append({
                    "entry_id": f"TE-{te_counter:08d}",
                    "timesheet_id": ts_id,
                    "emp_id": r.emp_id,
                    "work_date": iso(work_date),
                    "project_id": proj,
                    "wbs_id": ctx.rng.choice(wlist) if wlist and wlist[0] else None,
                    "cost_code_id": ctx.rng.choice(cclist) if cclist and cclist[0] else None,
                    "clock_in": iso(clock_in),
                    "clock_out": iso(clock_out),
                    "hours": hrs,
                    "overtime_hours": ot,
                    "origin_system": ORIGIN_SQLSERVER,
                })
                total += hrs
            ts_rows.append({
                "timesheet_id": ts_id,
                "emp_id": r.emp_id,
                "week_ending": iso(wk),
                "project_id": proj,
                "status": weighted_pick(ctx, {"Approved": 0.8, "Submitted": 0.15, "Rejected": 0.05}, 1)[0],
                "total_hours": round(total, 2),
                "origin_system": ORIGIN_SQLSERVER,
            })
    return pd.DataFrame(ts_rows), pd.DataFrame(te_rows)


def _build_labor_charges(ctx: ExtContext, time_entries: pd.DataFrame, employees: pd.DataFrame) -> pd.DataFrame:
    rate = employees.set_index("emp_id")["hourly_rate"].to_dict()
    te = time_entries.copy()
    te["week_ending"] = pd.to_datetime(te["work_date"]).apply(
        lambda d: (d + timedelta(days=(4 - d.weekday()) % 7)).date().isoformat())
    te["reg"] = te["hours"] - te["overtime_hours"]
    te["ot"] = te["overtime_hours"]
    te["amount"] = te.apply(
        lambda r: round(r["reg"] * rate.get(r["emp_id"], 55) + r["ot"] * rate.get(r["emp_id"], 55) * 1.5, 2),
        axis=1)
    grp = te.groupby(["project_id", "wbs_id", "cost_code_id", "week_ending"], dropna=False).agg(
        reg_hours=("reg", "sum"), ot_hours=("ot", "sum"), amount=("amount", "sum")).reset_index()
    grp["reg_hours"] = grp["reg_hours"].round(2)
    grp["ot_hours"] = grp["ot_hours"].round(2)
    grp["amount"] = grp["amount"].round(2)
    grp.insert(0, "charge_id", ids("LC-", len(grp), width=8))
    grp["origin_system"] = ORIGIN_SQLSERVER
    cols = ["charge_id", "project_id", "wbs_id", "cost_code_id", "week_ending",
            "reg_hours", "ot_hours", "amount", "origin_system"]
    return grp[cols]


def _emit_ddl():
    lines = [
        "-- Time Clock schema for on-prem SQL Server (mirrored into Microsoft Fabric).",
        "-- Fabric mirroring requires a primary key on every mirrored table.",
        "-- Run against your target database (e.g., TimeClockDB).",
        "",
        f"IF SCHEMA_ID('{SCHEMA}') IS NULL EXEC('CREATE SCHEMA {SCHEMA}');",
        "GO",
        "",
    ]
    for table, cols in DDL.items():
        lines.append(f"IF OBJECT_ID('{SCHEMA}.{table}', 'U') IS NOT NULL DROP TABLE {SCHEMA}.{table};")
        lines.append(f"CREATE TABLE {SCHEMA}.{table} (")
        col_lines = [f"    {c} {t}" for c, t in cols]
        pk = PRIMARY_KEYS[table]
        col_lines.append(f"    CONSTRAINT PK_{table} PRIMARY KEY ({pk})")
        lines.append(",\n".join(col_lines))
        lines.append(");")
        lines.append("GO")
        lines.append("")
    (OUT_ROOT / SUBDIR).mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / SUBDIR / "schema.sql").write_text("\n".join(lines))


def _emit_load_script():
    lines = [
        "-- Bulk-load the CSV extracts into the [timeclock] tables.",
        "-- Adjust @dir to the folder where you copied the CSV files on the SQL Server host.",
        "-- CSVs have a header row (FIRSTROW = 2) and are UTF-8, comma-delimited.",
        "",
        "DECLARE @dir NVARCHAR(400) = 'C:\\\\timeclock_csv\\\\';  -- <-- EDIT THIS PATH",
        "",
    ]
    for table in DDL.keys():
        lines.append(f"BULK INSERT {SCHEMA}.{table}")
        lines.append(f"FROM '{{@dir}}{table}.csv'".replace("{@dir}", "' + @dir + '"))
        lines.append("WITH (FORMAT = 'CSV', FIRSTROW = 2, FIELDTERMINATOR = ',', "
                     "ROWTERMINATOR = '0x0a', TABLOCK, CODEPAGE = '65001');")
        lines.append("GO")
        lines.append("")
    # BULK INSERT FROM needs a literal; provide a dynamic-SQL variant instead.
    dyn = [
        "-- NOTE: BULK INSERT requires a string literal for FROM. If the paths above",
        "-- error, use this dynamic-SQL pattern per table instead:",
        "--",
        "-- DECLARE @sql NVARCHAR(MAX) = N'BULK INSERT " + SCHEMA + ".employee FROM ''' + @dir +",
        "--   'employee.csv'' WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', "
        "ROWTERMINATOR=''0x0a'', CODEPAGE=''65001'');';",
        "-- EXEC sp_executesql @sql;",
    ]
    (OUT_ROOT / SUBDIR / "load_bulk.sql").write_text("\n".join(lines + dyn))


def generate(ctx: ExtContext) -> dict:
    employees = _build_employees(ctx)
    crews = _build_crews(ctx, employees)
    cost_codes = _build_cost_codes(ctx)
    timesheets, time_entries = _build_timesheets_entries(ctx, employees, cost_codes)
    labor_charges = _build_labor_charges(ctx, time_entries, employees)

    tables = {
        "employee": employees,
        "crew": crews,
        "cost_code": cost_codes,
        "timesheet": timesheets,
        "time_entry": time_entries,
        "labor_charge": labor_charges,
    }
    for name, df in tables.items():
        write_csv(df, SUBDIR, name)
    _emit_ddl()
    _emit_load_script()
    return tables
