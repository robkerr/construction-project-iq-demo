#!/usr/bin/env bash
#
# Provision the Amazon S3 "ods" landing zone that feeds the Fabric ELT pipeline
# (PL_ELT_Landing_to_Gold), and grant the existing least-privilege reader IAM
# user access to it.
#
# This is the THIRD ingestion pattern in the demo (a traditional ELT flow):
#
#     S3 s3://<bucket>/ods/*.parquet
#         --Fabric Copy activity-->  lakehouse Files/landing/
#         --02_load_bronze notebook--> bronze.*  (Delta)
#         --03_build_silver_gold notebook--> silver / gold
#
# Contrast with the other two patterns already in the workspace:
#   - BigQuery  -> Fabric mirroring (near-real-time replication)
#   - S3 permits (Delta) -> OneLake shortcuts (zero-copy virtualization)
#
# The ELT source reuses the SAME bucket and SAME reader IAM user as the permits
# shortcut; we just add a new "ods/" prefix and extend the read policy.
#
# Requires: aws CLI configured for account 107573631416.
set -euo pipefail

BUCKET="contoso-enc-external-permits-107573631416"
PREFIX="ods"
IAM_USER="fabric-s3-permits-reader"
IAM_POLICY="FabricPermitsReadOnly"
LOCAL_PARQUET_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../out/parquet" && pwd)"

echo "==> 1/3 Uploading landing Parquet -> s3://${BUCKET}/${PREFIX}/"
aws s3 cp "${LOCAL_PARQUET_DIR}/" "s3://${BUCKET}/${PREFIX}/" \
  --recursive --exclude "*" --include "*.parquet"

echo "==> 2/3 Extending IAM policy ${IAM_POLICY} on ${IAM_USER} to read ${PREFIX}/*"
POLICY_DOC="$(mktemp)"
cat > "${POLICY_DOC}" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ListPermitsBucket", "Effect": "Allow", "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${BUCKET}" },
    { "Sid": "ReadObjects", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": [
        "arn:aws:s3:::${BUCKET}/permits-delta/*",
        "arn:aws:s3:::${BUCKET}/permits/*",
        "arn:aws:s3:::${BUCKET}/${PREFIX}/*"
      ] }
  ]
}
EOF
aws iam put-user-policy --user-name "${IAM_USER}" \
  --policy-name "${IAM_POLICY}" --policy-document "file://${POLICY_DOC}"
rm -f "${POLICY_DOC}"

echo "==> 3/3 Verifying"
aws s3 ls "s3://${BUCKET}/${PREFIX}/"
echo
echo "Done. The Fabric connection 'Permitting_Data_S3' (AmazonS3, bucket root)"
echo "already has credentials for this bucket, so the Copy activity can read ${PREFIX}/."
echo "Create/refresh the pipeline with: python create_pipeline.py"
