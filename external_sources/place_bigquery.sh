#!/usr/bin/env bash
# Place the BigQuery work-order tables into a Google BigQuery dataset.
# Idempotent: creates the dataset if needed and --replace-loads each parquet table.
#
#   ./place_bigquery.sh
#
# Override via env: BQ_PROJECT, BQ_DATASET, BQ_LOCATION
set -euo pipefail

PROJECT="${BQ_PROJECT:-gen-lang-client-0875336337}"
DATASET="${BQ_DATASET:-epc_workorders}"
LOCATION="${BQ_LOCATION:-US}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/out/bigquery"

TABLES=(equipment_asset work_order work_order_task work_order_labor \
        work_order_material work_order_status_history)

echo "Project : $PROJECT"
echo "Dataset : $DATASET ($LOCATION)"
echo

echo "Ensuring dataset exists..."
bq --project_id="$PROJECT" --location="$LOCATION" mk -f --dataset "$PROJECT:$DATASET"

for t in "${TABLES[@]}"; do
  echo "Loading $DATASET.$t ..."
  bq --project_id="$PROJECT" load --source_format=PARQUET --replace \
     "$DATASET.$t" "$DIR/$t/$t.parquet"
done

echo
echo "Done. Tables in $PROJECT:$DATASET:"
bq --project_id="$PROJECT" ls "$DATASET"
