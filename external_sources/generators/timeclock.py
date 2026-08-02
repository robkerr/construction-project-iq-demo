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
DATABASE = "EmployeeTimeTracking"  # target database on the on-prem SQL Server
FABRIC_LOGIN = "fabric_login"       # existing server login Fabric uses to connect
FABRIC_USER = "fabric_user"         # database user mapped to FABRIC_LOGIN

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
    # BULK INSERT requires a STRING LITERAL for FROM (no variables/concatenation),
    # so we build each statement with dynamic SQL and run it via sp_executesql.
    # This keeps a single editable @dir while remaining valid T-SQL.
    lines = [
        "-- Bulk-load the CSV extracts into the [timeclock] tables.",
        "-- Requires SQL Server 2017+ (FORMAT = 'CSV').",
        "-- 1) Copy the six timeclock/*.csv files to a folder the SQL Server service",
        "--    account can read, then edit @dir below (keep the trailing backslash).",
        "-- 2) The CSVs are UTF-8 with a header row (FIRSTROW = 2) and Unix (LF) line",
        "--    endings. If your files have Windows (CRLF) endings, change @row to '0x0d0a'.",
        "",
        "SET NOCOUNT ON;",
        "DECLARE @dir NVARCHAR(400) = N'C:\\timeclock_csv\\';  -- <-- EDIT THIS PATH",
        "DECLARE @row NVARCHAR(10)  = N'0x0a';                 -- LF; use '0x0d0a' for CRLF files",
        "DECLARE @sql NVARCHAR(MAX);",
        "",
    ]
    for table in DDL.keys():
        lines.append(
            f"SET @sql = N'BULK INSERT {SCHEMA}.{table} FROM ''' + @dir + N'{table}.csv'' "
            "WITH (FORMAT=''CSV'', FIRSTROW=2, FIELDTERMINATOR='','', ROWTERMINATOR=''' "
            "+ @row + N''', TABLOCK, CODEPAGE=''65001'');';"
        )
        lines.append("EXEC sys.sp_executesql @sql;")
        lines.append("")
    lines.append("PRINT 'Time clock load complete.';")
    (OUT_ROOT / SUBDIR / "load_bulk.sql").write_text("\n".join(lines))


def _emit_mirroring_scripts():
    """Emit the Fabric Mirroring (CDC) prep scripts for SQL Server 2016-2022.

    Three ordered files in out/sqlserver/:
      mirroring_01_enable_cdc.sql   - enable CDC on the database + each table
      mirroring_02_security.sql     - map fabric_login -> fabric_user, minimal grants
      mirroring_03_verify_cdc.sql   - verification queries
    """
    folder = OUT_ROOT / SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    tables = list(DDL.keys())
    values = ",".join(f"(N'{t}')" for t in tables)

    # ---- 01: enable CDC ----
    enable = f"""/* ============================================================
   Fabric Mirroring prep - STEP 1: Enable Change Data Capture (CDC)
   Database : {DATABASE}
   Schema   : {SCHEMA}
   ------------------------------------------------------------
   SQL Server 2016-2022 uses CDC for Fabric Mirroring.
   Run this as a SYSADMIN (e.g., sa). Enabling CDC up front means the Fabric
   login itself does NOT need sysadmin - see mirroring_02_security.sql.
   REQUIREMENT: SQL Server Agent must be RUNNING (CDC capture/cleanup jobs run
   under Agent). Set Agent to Automatic startup.
   Idempotent: safe to re-run.
   ============================================================ */
USE [{DATABASE}];
GO

-- 0) SQL Server Agent must be running for CDC.
IF NOT EXISTS (
    SELECT 1 FROM sys.dm_server_services
    WHERE servicename LIKE N'SQL Server Agent%' AND status_desc = N'Running')
    PRINT 'WARNING: SQL Server Agent is not running. Start it (Automatic startup recommended) before mirroring.';
GO

-- 1) Enable CDC at the database level.
IF (SELECT is_cdc_enabled FROM sys.databases WHERE name = DB_NAME()) = 0
BEGIN
    EXEC sys.sp_cdc_enable_db;
    PRINT 'CDC enabled at database level.';
END
ELSE
    PRINT 'CDC already enabled at database level.';
GO

-- 2) Enable CDC on each mirrored table.
--    @role_name = NULL -> access to change data is gated only by SELECT on the
--    table, so the read-only fabric_user (granted SELECT in step 2) can read it.
--    @supports_net_changes = 1 requires a primary key (all timeclock tables have one).
DECLARE @schema SYSNAME = N'{SCHEMA}';
DECLARE @tables TABLE (name SYSNAME);
INSERT INTO @tables (name) VALUES {values};

DECLARE @t SYSNAME;
DECLARE tcur CURSOR LOCAL FAST_FORWARD FOR SELECT name FROM @tables;
OPEN tcur;
FETCH NEXT FROM tcur INTO @t;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM sys.tables tt
        JOIN sys.schemas ss ON ss.schema_id = tt.schema_id
        WHERE ss.name = @schema AND tt.name = @t AND tt.is_tracked_by_cdc = 1)
    BEGIN
        EXEC sys.sp_cdc_enable_table
             @source_schema        = @schema,
             @source_name          = @t,
             @role_name            = NULL,
             @supports_net_changes = 1;
        PRINT 'CDC enabled on ' + @schema + '.' + @t;
    END
    ELSE
        PRINT 'CDC already enabled on ' + @schema + '.' + @t;
    FETCH NEXT FROM tcur INTO @t;
END
CLOSE tcur;
DEALLOCATE tcur;
GO

PRINT 'STEP 1 complete: CDC enabled. Next run mirroring_02_security.sql.';
GO
"""
    (folder / "mirroring_01_enable_cdc.sql").write_text(enable)

    # ---- 02: security ----
    security = f"""/* ============================================================
   Fabric Mirroring prep - STEP 2: Security for the Fabric login
   Database : {DATABASE}
   ------------------------------------------------------------
   Because CDC is pre-enabled (STEP 1), the Fabric login needs only the MINIMAL
   privileges documented for SQL Server 2016-2022 mirroring:
       Server level  : CONNECT SQL
       Database level: CONNECT, SELECT
   (No sysadmin / db_owner required once CDC already exists.)
   Run this as a SYSADMIN. Idempotent: safe to re-run.
   ============================================================ */

-- 2a) SERVER LEVEL: allow the existing [{FABRIC_LOGIN}] login to connect.
USE [master];
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'{FABRIC_LOGIN}')
BEGIN
    PRINT 'NOTE: server login [{FABRIC_LOGIN}] not found. Create it first, e.g.:';
    PRINT '  CREATE LOGIN [{FABRIC_LOGIN}] WITH PASSWORD = ''<strong password>'';';
END
ELSE
BEGIN
    GRANT CONNECT SQL TO [{FABRIC_LOGIN}];
    PRINT 'Granted CONNECT SQL to [{FABRIC_LOGIN}].';
END
GO

-- 2b) DATABASE LEVEL: map a database user to the login and grant read access.
USE [{DATABASE}];
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'{FABRIC_USER}')
BEGIN
    CREATE USER [{FABRIC_USER}] FOR LOGIN [{FABRIC_LOGIN}];
    PRINT 'Created database user [{FABRIC_USER}] for login [{FABRIC_LOGIN}].';
END
ELSE
    PRINT 'Database user [{FABRIC_USER}] already exists.';
GO

-- Database-scoped SELECT covers the timeclock tables AND the cdc.* change tables.
GRANT CONNECT, SELECT TO [{FABRIC_USER}];
GO

PRINT 'STEP 2 complete: [{FABRIC_LOGIN}] can connect and read. Next run mirroring_03_verify_cdc.sql.';
GO
"""
    (folder / "mirroring_02_security.sql").write_text(security)

    # ---- 03: verify ----
    verify = f"""/* ============================================================
   Fabric Mirroring prep - STEP 3: Verify CDC & permissions
   Database : {DATABASE}
   Run each query and confirm the expected results noted in comments.
   ============================================================ */
USE [{DATABASE}];
GO

-- (a) Database-level CDC flag. Expect is_cdc_enabled = 1.
SELECT name, is_cdc_enabled
FROM sys.databases
WHERE name = DB_NAME();

-- (b) Per-table CDC status. Expect one row per mirrored table, is_tracked_by_cdc = 1.
SELECT s.name AS [schema], t.name AS [table], t.is_tracked_by_cdc
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id = t.schema_id
WHERE s.name = N'{SCHEMA}'
ORDER BY t.name;

-- (c) CDC capture instances. Expect one per table, supports_net_changes = 1.
SELECT ct.capture_instance,
       source_schema = OBJECT_SCHEMA_NAME(ct.source_object_id),
       source_table  = OBJECT_NAME(ct.source_object_id),
       ct.supports_net_changes
FROM cdc.change_tables ct
ORDER BY ct.capture_instance;

-- (d) CDC Agent jobs. Expect a capture job and a cleanup job for this database.
EXEC sys.sp_cdc_help_jobs;

-- (e) SQL Server Agent must be running (required for CDC).
SELECT servicename, status_desc
FROM sys.dm_server_services
WHERE servicename LIKE N'SQL Server Agent%';

-- (f) Fabric user permissions. Expect CONNECT + SELECT granted to {FABRIC_USER}.
SELECT dp.name AS db_user, dp.type_desc,
       perm.permission_name, perm.state_desc
FROM sys.database_permissions perm
JOIN sys.database_principals dp ON dp.principal_id = perm.grantee_principal_id
WHERE dp.name = N'{FABRIC_USER}'
ORDER BY perm.permission_name;
GO
"""
    (folder / "mirroring_03_verify_cdc.sql").write_text(verify)


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
    _emit_mirroring_scripts()
    return tables
