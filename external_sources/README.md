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
| 3 | Amazon **S3** (Delta Lake) | Government permits & inspections | **Shortcut** into bronze Tables | `place_s3.sh` + `convert_s3_to_delta.py` + `place_s3_delta.sh` (automated) |
| 4 | Amazon **S3** (raw Parquet, `ods/`) | Core project/SAP landing data | **ELT pipeline** → Copy into Files/landing → notebooks | `elt_pipeline/` (automated) |

These cover the three headline ingestion patterns side by side: **mirroring**
(#1–2, near-real-time replication), **shortcuts** (#3, zero-copy virtualization),
and a **traditional ELT data pipeline** (#4, Copy + notebook orchestration).

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
  s3/permits/<table>/<table>.parquet                  (6 permit tables, raw parquet)
  s3_delta/permits/<table>/                           (6 permit tables, Delta Lake)
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

1. Create/choose a database (e.g. `EmployeeTimeTracking`).
2. Create the schema + tables:
   ```
   sqlcmd -S <server> -d EmployeeTimeTracking -i out/sqlserver/schema.sql
   ```
3. Copy the six `out/sqlserver/*.csv` files to a folder the SQL Server service
   account can read (e.g. `C:\timeclock_csv\`), edit the `@dir` variable at the
   top of `out/sqlserver/load_bulk.sql`, then:
   ```
   sqlcmd -S <server> -d EmployeeTimeTracking -i out/sqlserver/load_bulk.sql
   ```
   (`load_bulk.sql` uses dynamic SQL + `sp_executesql` because `BULK INSERT`
   requires a string literal for `FROM`. Alternatively:
   `bcp <table> in <file>.csv -c -t, -F 2 -S <server> -d EmployeeTimeTracking`.)

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

### B. Mirror SQL Server → bronze (SQL Server 2022 = CDC-based)
Prep the on-prem instance first (run in order, as a sysadmin, against
`EmployeeTimeTracking`). SQL Server 2016-2022 mirroring replicates via **Change
Data Capture**, so CDC must be enabled and **SQL Server Agent must be running**:

```
sqlcmd -S <server> -d EmployeeTimeTracking -i out/sqlserver/mirroring_01_enable_cdc.sql
sqlcmd -S <server> -d EmployeeTimeTracking -i out/sqlserver/mirroring_02_security.sql
sqlcmd -S <server> -d EmployeeTimeTracking -i out/sqlserver/mirroring_03_verify_cdc.sql
```

- `mirroring_01_enable_cdc.sql` — enables CDC at the database level and on all
  six `timeclock` tables (idempotent).
- `mirroring_02_security.sql` — grants the existing `fabric_login` server-level
  `CONNECT SQL`, maps it to a `fabric_user` database user, and grants `CONNECT,
  SELECT`. Because CDC is pre-enabled, **`fabric_login` never needs sysadmin**.
- `mirroring_03_verify_cdc.sql` — verification queries (DB flag, per-table CDC,
  capture instances, CDC Agent jobs, Agent status, `fabric_user` grants).

Then in Fabric:
1. **Create → Mirrored SQL Server database**, enter the source database name.
2. **New connection → SQL Server database**, select your **on-premises data
   gateway**, authenticate as `fabric_login`, check **Use encrypted connection**.
3. Select the `timeclock.*` tables and start mirroring. Wait for replication.
4. In the **bronze** lakehouse → **New shortcut → Microsoft OneLake** → point at
   the mirrored `timeclock.*` tables.

### C. Shortcut S3 → bronze (as true queryable tables via Delta Lake)

> **Why Delta?** OneLake shortcuts placed in the lakehouse **Tables** section are
> only recognized as tables when the source is **Delta Lake** format (a folder
> with a `_delta_log`). Raw parquet works only as a **Files** shortcut. To make
> the permits appear as real, queryable `bronze.*` tables with **zero copy**, the
> data is published to S3 in Delta format.

**1. Convert the permit parquet to Delta and upload to S3** (automated):

```bash
./.venv/bin/python external_sources/convert_s3_to_delta.py   # writes out/s3_delta/permits/<table>/
external_sources/place_s3_delta.sh                            # uploads to s3://<bucket>/permits-delta/<table>/
```

This produces six Delta tables (each `_delta_log` + one parquet part) at
`s3://contoso-enc-external-permits-107573631416/permits-delta/<table>/`.

**2. Create an Amazon S3 connection in Fabric** (portal): Settings → Manage
connections and gateways → New → **Amazon S3**. Provide an access key/secret with
read access to the bucket.

**3. Create one shortcut per table in the bronze lakehouse** (portal): open the
schema-enabled **bronze** lakehouse → under **Tables → bronze** →
**New shortcut → Amazon S3** → use the connection from step 2, then point each
shortcut at a Delta table folder:

```
s3://contoso-enc-external-permits-107573631416/permits-delta/authority/
s3://contoso-enc-external-permits-107573631416/permits-delta/permit/
s3://contoso-enc-external-permits-107573631416/permits-delta/inspection/
s3://contoso-enc-external-permits-107573631416/permits-delta/code_violation/
s3://contoso-enc-external-permits-107573631416/permits-delta/permit_fee/
s3://contoso-enc-external-permits-107573631416/permits-delta/environmental_reading/
```

Each lands as a queryable table: `bronze.authority`, `bronze.permit`,
`bronze.inspection`, `bronze.code_violation`, `bronze.permit_fee`,
`bronze.environmental_reading` — no data movement (the bytes stay in S3).

> Tip: point the shortcut at the **table folder** (the one containing
> `_delta_log`), not the parent `permits-delta/` prefix.

Once wired, all three sources join to the existing model on `project_id` /
`wbs_id` / `equipment_tag` / `supplier_id` — demonstrating a single OneLake view
over BigQuery + SQL Server + S3 + the existing SAP/non-SAP data.

---

### D. ELT pipeline: S3 `ods/` → Files/landing → bronze/silver/gold

The third ingestion pattern is a **traditional ELT data pipeline** — not
mirroring, not shortcuts. It shows the classic "land, then transform" flow that
most teams already know, running natively on Fabric compute.

```
s3://contoso-enc-external-permits-107573631416/ods/*.parquet
    │  (Fabric Copy activity, source connection "Permitting_Data_S3")
    ▼
lh_project_intelligence  Files/landing/*.parquet
    │  (notebook 02_load_bronze)
    ▼
bronze.<table>  (Delta)
    │  (notebook 03_build_silver_gold)
    ▼
silver.* / gold.*
```

**Artifacts** (in `elt_pipeline/`):

| File | Purpose |
|------|---------|
| `pipeline-content.json` | The Fabric DataPipeline definition (Copy → 02 → 03, chained on Succeeded). |
| `create_pipeline.py` | Creates/updates the pipeline `PL_ELT_Landing_to_Gold` via the Fabric REST API (Entra auth, no secrets). `--verify` prints the deployed activity graph. |
| `setup_s3_ods.sh` | Uploads `out/parquet/*.parquet` to the S3 `ods/` prefix and extends the reader IAM policy. |

**Security model** (all real, no account keys):

- **Source (S3):** reuses the existing least-privilege IAM user
  `fabric-s3-permits-reader`; its `FabricPermitsReadOnly` policy was extended to
  allow `s3:GetObject` on `ods/*` (in addition to `permits/*` and
  `permits-delta/*`). The pipeline's Copy source reuses the existing Fabric
  Amazon S3 connection **`Permitting_Data_S3`**
  (`4debad80-8aef-46cc-b581-c9298361bb6f`).
- **Sink (lakehouse):** the Copy activity writes to
  `lh_project_intelligence` (`3ecdff20-93ee-4f5a-81e7-c022007d128b`) using the
  Fabric workspace's own identity — no keys, no external storage.
- **Pipeline creation:** `create_pipeline.py` authenticates with your `az`
  login (`az account get-access-token`). Nothing sensitive is committed.

**Build it (does not run it):**

```bash
# 1. Land the parquet in S3 and grant read (one-time)
external_sources/elt_pipeline/setup_s3_ods.sh

# 2. Create the pipeline in Fabric (idempotent — updates if it exists)
./.venv/bin/python external_sources/elt_pipeline/create_pipeline.py

# 3. Inspect what was deployed
./.venv/bin/python external_sources/elt_pipeline/create_pipeline.py --verify
```

The pipeline `PL_ELT_Landing_to_Gold` is created but **intentionally not
triggered** — run it manually from the Fabric portal to demo the full ELT path.
The Copy activity flattens `ods/*.parquet` into `Files/landing/<table>.parquet`
(PreserveHierarchy), which is exactly what `02_load_bronze` expects.
