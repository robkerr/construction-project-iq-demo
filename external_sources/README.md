# External Data Sources — OneLake Virtualization Demo

This folder generates and places **three external data sources** so the demo can
show how Microsoft Fabric **OneLake virtualizes data from multiple systems**
(mirroring + shortcuts) into a single **bronze** lakehouse — without copying it
into the demo's own store.

Everything is **100% synthetic**, deterministic (**seed 42**, `today = 2026-08-01`),
and every row references the **real keys** produced by `data_gen/generate.py`
(`project_id`, `wbs_id`, `supplier_id`, `equipment_tag`). Project **Falcon
(PRJ-001)** and the hero transformer **ET-1001** appear in all three sources so
you can fuse them with the existing Fabric model in one query.

| # | Source system | Subject | Into Fabric via | Placed by |
|---|---------------|---------|-----------------|-----------|
| 1 | Google **BigQuery** | Work-order management | **Mirroring** → shortcut in bronze | `place_bigquery.sh` (automated) |
| 2 | On-prem **SQL Server** | Time clock / labor | **Mirroring** → shortcut in bronze | You run `schema.sql` + `load_bulk.sql` |
| 3 | Amazon **S3** (Parquet) | Government permits & inspections | **Shortcut** from bronze | `place_s3.sh` (automated) |

## Regenerate the data

```bash
# from the repo root, with the project venv active
python data_gen/generate.py            # (re)build core out/ keys first
python external_sources/generate_external.py
```

Outputs land in `external_sources/out/`:

```
out/
  bigquery/<table>/<table>.parquet   + <table>.csv   (6 work-order tables)
  sqlserver/<table>.csv  + schema.sql + load_bulk.sql (6 time-clock tables)
  s3/permits/<table>/<table>.parquet                  (6 permit tables)
  manifest.json
```

## Tables & key tie-ins

**1. BigQuery — work orders** (`origin_system = GCP-BigQuery`)
`equipment_asset` (incl. ET-1001), `work_order`, `work_order_task`,
`work_order_labor`, `work_order_material` (→ `supplier_id`),
`work_order_status_history`.
Falcon hero: emergency/critical WO `WO-900001` on **ET-1001**.

**2. SQL Server — time clock** (`origin_system = OnPrem-SQLServer`, schema `[timeclock]`)
`employee`, `crew`, `cost_code`, `timesheet`, `time_entry` (→ `project_id`/`wbs_id`),
`labor_charge`. Falcon shows an **overtime crunch** (Saturday OT) matching its at-risk story.

**3. S3 — permits & inspections** (`origin_system = External-Gov-S3`)
`authority`, `permit`, `inspection`, `code_violation`, `permit_fee`,
`environmental_reading`. Falcon hero: **failed environmental inspection**
(`INS-900001`) + **open critical violation** (`VIO-900001`) + turbidity exceedances.

---

## Placement

### 1) BigQuery (automated)
```bash
cd external_sources
./place_bigquery.sh          # project gen-lang-client-0875336337, dataset epc_workorders
```
Override with `BQ_PROJECT`, `BQ_DATASET`, `BQ_LOCATION`.

### 3) S3 (automated)
```bash
cd external_sources
./place_s3.sh                # bucket contoso-enc-external-permits-107573631416, prefix permits/
```
Override with `S3_BUCKET`, `AWS_REGION`, `S3_PREFIX`.

### 2) SQL Server (manual — no reachable server from this environment)
On a host that can reach your SQL Server instance:

1. Create/choose a database (e.g. `TimeClockDB`).
2. Create the schema + tables:
   ```
   sqlcmd -S <server> -d TimeClockDB -i out/sqlserver/schema.sql
   ```
3. Copy the six `out/sqlserver/*.csv` files to a folder the SQL Server service
   account can read (e.g. `C:\timeclock_csv\`), edit the `@dir` variable at the
   top of `out/sqlserver/load_bulk.sql`, then:
   ```
   sqlcmd -S <server> -d TimeClockDB -i out/sqlserver/load_bulk.sql
   ```
   (If `BULK INSERT` can't see the path, use the dynamic-SQL variant noted at the
   bottom of the script, or `bcp <table> in <file>.csv -c -t, -F 2 -S <server> -d TimeClockDB`.)

Every mirrored table already has a **primary key** (required by Fabric mirroring).

---

## Wire into the bronze lakehouse (Fabric portal)

> Rule for this demo: **shortcut data → shortcut FROM the bronze schema; mirrored
> data → presented IN bronze** (bronze shortcuts may point at the mirrored tables).

### A. Mirror BigQuery → bronze
1. Fabric workspace → **New item → Mirrored Database → Google BigQuery**.
2. Authenticate to project `gen-lang-client-0875336337`, select dataset
   `epc_workorders`, mirror all six tables. Wait for initial replication.
3. In the **bronze** lakehouse → **New shortcut → Microsoft OneLake** → point at
   the mirrored database's tables (e.g. under `bronze/Tables/wo_*`).

### B. Mirror SQL Server → bronze
1. Fabric workspace → **New item → Mirrored Database → SQL Server**
   (via **on-premises data gateway** for an on-prem instance).
2. Select the `[timeclock]` tables, mirror. Wait for replication.
3. In the **bronze** lakehouse → **New shortcut → Microsoft OneLake** → point at
   the mirrored `timeclock.*` tables.

### C. Shortcut S3 → bronze
1. In the **bronze** lakehouse → **New shortcut → Amazon S3**.
2. URL `https://contoso-enc-external-permits-107573631416.s3.us-east-1.amazonaws.com/`
   (or `s3://contoso-enc-external-permits-107573631416/permits/`), supply an
   access key/secret with read access.
3. Point the shortcut at the `permits/` prefix; the six `<table>/` folders appear
   as shortcut tables in bronze.

Once wired, all three sources join to the existing model on `project_id` /
`wbs_id` / `equipment_tag` / `supplier_id` — demonstrating a single OneLake view
over BigQuery + SQL Server + S3 + the existing SAP/non-SAP data.
