#!/usr/bin/env bash
# Tear down the GCP resources created by setup_bigquery_service_account.sh.
#
# Usage:
#   ./remove_bigquery_service_account.sh <PROJECT_ID> <DATASET_ID> <SERVICE_ACCOUNT_NAME> [--delete-bucket]
#
# This script:
#   1. Deletes the service account (and its keys)
#   2. Deletes the custom IAM role (FabricBigQueryMirror)
#   3. Removes the local JSON key file
#   4. Optionally deletes the GCS staging bucket (--delete-bucket)
#   5. Optionally disables change history on the dataset tables (--disable-cdc)
#
# By default the staging bucket and change-history settings are left intact
# (they are harmless and cheap). Pass the flags to remove them too.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - bq CLI available (only needed for --disable-cdc)
#
# For this demo:
#   ./remove_bigquery_service_account.sh gen-lang-client-0875336337 epc_workorders svc-fabric-bq-mirror

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <PROJECT_ID> <DATASET_ID> <SERVICE_ACCOUNT_NAME> [--delete-bucket] [--disable-cdc]"
  echo ""
  echo "  Set FABRIC_BQ_ROLE_ID to match the role ID used at setup time"
  echo "  (default: FabricBigQueryMirror; this demo used FabricBigQueryMirrorV2)."
  exit 1
fi

PROJECT_ID="$1"
DATASET_ID="$2"
SA_NAME="$3"
shift 3

DELETE_BUCKET=false
DISABLE_CDC=false
for arg in "$@"; do
  case "$arg" in
    --delete-bucket) DELETE_BUCKET=true ;;
    --disable-cdc)   DISABLE_CDC=true ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
CUSTOM_ROLE_ID="${FABRIC_BQ_ROLE_ID:-FabricBigQueryMirror}"
KEY_FILE="${SA_NAME}-key.json"
STAGING_BUCKET="${PROJECT_ID}_fabric_staging_bucket"

echo "=== Setting project to ${PROJECT_ID} ==="
gcloud config set project "${PROJECT_ID}"

# -- 1. Delete service account -----------------------------------------------
echo ""
echo "=== Deleting service account: ${SA_EMAIL} ==="
gcloud iam service-accounts delete "${SA_EMAIL}" --quiet \
  2>/dev/null && echo "  Deleted." \
  || echo "  (Service account not found or already deleted, continuing...)"

# -- 2. Delete custom IAM role -----------------------------------------------
echo ""
echo "=== Deleting custom IAM role: ${CUSTOM_ROLE_ID} ==="
gcloud iam roles delete "${CUSTOM_ROLE_ID}" --project="${PROJECT_ID}" --quiet \
  2>/dev/null && echo "  Deleted (soft-delete; purges after ~7 days)." \
  || echo "  (Role not found or already deleted, continuing...)"

# -- 3. Remove local key file ------------------------------------------------
echo ""
echo "=== Removing local key file ==="
if [ -f "${KEY_FILE}" ]; then
  rm -f "${KEY_FILE}"
  echo "  Removed ${KEY_FILE}."
else
  echo "  ${KEY_FILE} not present, skipping."
fi

# -- 4. Optionally delete staging bucket -------------------------------------
echo ""
if [ "${DELETE_BUCKET}" = true ]; then
  echo "=== Deleting staging bucket: gs://${STAGING_BUCKET} ==="
  gcloud storage rm --recursive "gs://${STAGING_BUCKET}" --quiet \
    2>/dev/null && echo "  Deleted." \
    || echo "  (Bucket not found or already deleted, continuing...)"
else
  echo "=== Staging bucket left intact: gs://${STAGING_BUCKET} ==="
  echo "  (Pass --delete-bucket to remove it.)"
fi

# -- 5. Optionally disable change history ------------------------------------
echo ""
if [ "${DISABLE_CDC}" = true ]; then
  echo "=== Disabling change history on tables in ${DATASET_ID} ==="
  TABLES=$(bq ls --format=json "${PROJECT_ID}:${DATASET_ID}" \
    | python3 -c "import json,sys; print('\n'.join(t['tableReference']['tableId'] for t in json.load(sys.stdin) if t.get('type')=='TABLE'))")
  for TABLE in ${TABLES}; do
    echo "  - ${TABLE}"
    bq query --use_legacy_sql=false \
      "ALTER TABLE \`${PROJECT_ID}.${DATASET_ID}.${TABLE}\` SET OPTIONS (enable_change_history = FALSE)" \
      >/dev/null 2>&1 || echo "    (failed, continuing...)"
  done
  echo "  Done."
else
  echo "=== Change history left enabled on dataset tables ==="
  echo "  (Pass --disable-cdc to turn it off.)"
fi

echo ""
echo "=== Teardown complete ==="
