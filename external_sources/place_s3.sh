#!/usr/bin/env bash
# Place the government permit/inspection parquet files into an Amazon S3 bucket.
# Idempotent: creates the bucket if needed and copies each table's parquet under
# s3://<bucket>/<prefix>/<table>/. Fabric shortcuts the <prefix> folder into bronze.
#
#   ./place_s3.sh
#
# Override via env: S3_BUCKET, AWS_REGION, S3_PREFIX
set -euo pipefail

BUCKET="${S3_BUCKET:-contoso-enc-external-permits-107573631416}"
REGION="${AWS_REGION:-us-east-1}"
PREFIX="${S3_PREFIX:-permits}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/out/s3/permits"

TABLES=(authority permit inspection code_violation permit_fee environmental_reading)

echo "Bucket : s3://$BUCKET  ($REGION)"
echo "Prefix : $PREFIX"
echo

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket already exists."
else
  echo "Creating bucket..."
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
fi

for t in "${TABLES[@]}"; do
  echo "Uploading $t ..."
  aws s3 cp "$DIR/$t/$t.parquet" "s3://$BUCKET/$PREFIX/$t/$t.parquet"
done

echo
echo "Done. Objects under s3://$BUCKET/$PREFIX/:"
aws s3 ls "s3://$BUCKET/$PREFIX/" --recursive
