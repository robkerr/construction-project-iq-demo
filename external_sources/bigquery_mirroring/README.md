# BigQuery → Fabric Mirroring Toolkit

Automates the setup for mirroring the `epc_workorders` Google BigQuery dataset
into Microsoft Fabric OneLake, so it can be surfaced as external work-order data
in the Contoso E&C demo.

This toolkit is adapted from the proven scripts at
[robkerr/fabric-data-integration-scripts](https://github.com/robkerr/fabric-data-integration-scripts/tree/main/bigquery_mirroring),
with the project/dataset defaults filled in for this demo.

## What gets mirrored

The `epc_workorders` dataset (US multi-region, project `gen-lang-client-0875336337`),
containing 6 tables:

| Table | Description |
|-------|-------------|
| `equipment_asset` | Equipment/asset master |
| `work_order` | Work order headers |
| `work_order_task` | Tasks within a work order |
| `work_order_labor` | Labor charged to work orders |
| `work_order_material` | Materials charged to work orders |
| `work_order_status_history` | Work order status transitions |

Work orders reference the same project codes used elsewhere in the demo, so the
mirrored data ties into the existing Fabric lakehouse.

## How mirroring works

Fabric reads the BigQuery **change history** (CDC) via a dedicated GCP service
account, stages exports in a GCS bucket, and replicates the tables into OneLake
as Delta. This requires:

1. A service account with a minimal custom IAM role.
2. A GCS staging bucket in the **same region** as the dataset.
3. `enable_change_history = TRUE` on every table.
4. A **Google BigQuery connection** in Fabric (SA email + JSON key).
5. A **Mirrored Google BigQuery** item in a Fabric workspace.

Steps 1-3 are automated by `setup_bigquery_service_account.sh`.
Steps 4-5 are **portal-only** (done by you in the Fabric UI).
Starting / stopping / status is automated by `setup_bigquery_mirror.py`.

## Files

| File | Purpose |
|------|---------|
| `setup_bigquery_service_account.sh` | GCP-side setup: SA, IAM role, staging bucket, enable CDC, JSON key |
| `remove_bigquery_service_account.sh` | Teardown of the GCP resources above |
| `setup_bigquery_mirror.py` | Fabric REST driver: start/stop/status, list connections & mirrored DBs |
| `run.sh` | venv wrapper for the Python driver |
| `mirroring.yaml` | Config: workspace + mirrored database IDs |
| `requirements.txt` | Python deps (`pyyaml`) |

## Step 1 — GCP setup (automated)

```bash
cd external_sources/bigquery_mirroring
./setup_bigquery_service_account.sh gen-lang-client-0875336337 epc_workorders svc-fabric-bq-mirror
```

The script prints the **service account email**, the **JSON key file path**
(`svc-fabric-bq-mirror-key.json`), and the **staging bucket**. Keep the key file
secure — it is gitignored and must never be committed.

> **Already provisioned for this demo.** The GCP resources below already exist:
> - Service account: `svc-fabric-bq-mirror@gen-lang-client-0875336337.iam.gserviceaccount.com`
> - Custom IAM role: `FabricBigQueryMirrorV2`
> - Staging bucket: `gs://gen-lang-client-0875336337_fabric_staging_bucket` (US)
> - Change history enabled on all 6 `epc_workorders` tables
> - Local key file: `svc-fabric-bq-mirror-key.json`
>
> The role ID is `FabricBigQueryMirrorV2` (the default `FabricBigQueryMirror` was
> stuck in GCP's soft-deleted reserved state). The role ID is overridable via a
> 4th positional arg or the `FABRIC_BQ_ROLE_ID` env var on both scripts.

## Step 2 — Fabric connection + mirrored item (manual, portal)

In the Fabric portal:

1. **Create a connection**: Settings → Manage connections and gateways → New →
   **Google BigQuery**. Authentication = *Service Account*. Paste the SA email
   and the full contents of `svc-fabric-bq-mirror-key.json`.
2. **Create the mirrored item**: In your workspace, **New → Mirrored Google
   BigQuery**. Select the connection, project `gen-lang-client-0875336337`,
   dataset `epc_workorders`, and the tables to mirror. Save.

## Step 3 — Fill in mirroring.yaml

```bash
# Find the mirrored database ID (NOT the SQL endpoint) in your workspace:
./run.sh --list-mirrored-databases --workspace <WORKSPACE_ID>
```

Copy the workspace ID and MirroredDatabase ID into `mirroring.yaml`.

> Fabric creates a companion **SQLEndpoint** item with the same name — always
> use the **MirroredDatabase** ID here.

## Step 4 — Start & monitor (automated)

```bash
./run.sh mirroring.yaml            # start mirroring and poll per-table status
./run.sh mirroring.yaml --status   # status only
./run.sh mirroring.yaml --stop     # stop mirroring
```

Useful helpers:

```bash
./run.sh --list-connections                 # find the BigQuery connection GUID
./run.sh --list-connections --filter BigQuery
```

## Teardown

```bash
./remove_bigquery_service_account.sh gen-lang-client-0875336337 epc_workorders svc-fabric-bq-mirror
# add --delete-bucket and/or --disable-cdc to also remove those
```

## Prerequisites

- `gcloud` + `bq` CLIs, authenticated to project `gen-lang-client-0875336337`.
- Azure CLI (`az`) signed in to the Fabric tenant (used for API tokens).
- Python 3 (the `run.sh` wrapper creates its own `.venv`).
