#!/usr/bin/env bash
# Upload the Delta-formatted permit tables to Amazon S3 so they can be shortcut
# into the bronze lakehouse Tables section as true queryable tables.
#
# Delta tables are produced by convert_s3_to_delta.py under
# external_sources/out/s3_delta/permits/<table>/ (parquet + _delta_log).
# This script syncs each table folder to:
#   s3://<bucket>/<prefix>/<table>/
#
#   ./place_s3_delta.sh
#
# Override via env: S3_BUCKET, AWS_REGION, S3_DELTA_PREFIX
set -euo pipefail

BUCKET="${S3_BUCKET:-contoso-enc-external-permits-107573631416}"
REGION="${AWS_REGION:-us-east-1}"
PREFIX="${S3_DELTA_PREFIX:-permits-delta}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/out/s3_delta/permits"

TABLES=(authority permit inspection code_violation permit_fee environmental_reading)

echo "Bucket : s3://$BUCKET  ($REGION)"
echo "Prefix : $PREFIX  (Delta Lake tables)"
echo

if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "ERROR: bucket s3://$BUCKET not found. Run place_s3.sh first." >&2
  exit 1
fi

for t in "${TABLES[@]}"; do
  if [ ! -d "$DIR/$t/_delta_log" ]; then
    echo "ERROR: $DIR/$t is not a Delta table (no _delta_log). Run convert_s3_to_delta.py first." >&2
    exit 1
  fi
  echo "Syncing $t ..."
  # --delete keeps the S3 folder an exact mirror of the local Delta table.
  aws s3 sync "$DIR/$t/" "s3://$BUCKET/$PREFIX/$t/" --delete
done

echo
echo "Done. Delta tables under s3://$BUCKET/$PREFIX/:"
aws s3 ls "s3://$BUCKET/$PREFIX/" --recursive | grep _delta_log | head
