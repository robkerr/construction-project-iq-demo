#!/usr/bin/env bash
#
# Deploy the RTI commissioning-telemetry KQL schema to the eh_rti_telemetry
# database. Executes each statement in kql/schema.kql via the Kusto management
# REST endpoint using your Azure CLI login (no secrets).
#
# Usage: ./deploy_kql.sh
set -euo pipefail

CLUSTER_URI="https://trd-psr494w5ftntwyskww.z3.kusto.fabric.microsoft.com"
DB="eh_rti_telemetry"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA="${HERE}/kql/schema.kql"

TOKEN="$(az account get-access-token --resource https://kusto.kusto.windows.net --query accessToken -o tsv)"

# Parse schema.kql into individual statements: statements are separated by blank
# lines; comment lines starting with // are stripped. A statement may span lines.
python3 - "$SCHEMA" <<'PY' > /tmp/rti_stmts.txt
import sys
stmts, cur = [], []
for line in open(sys.argv[1]):
    s = line.rstrip("\n")
    if s.strip().startswith("//"):
        continue
    if s.strip() == "":
        if cur:
            stmts.append("\n".join(cur).strip()); cur = []
        continue
    cur.append(s)
if cur:
    stmts.append("\n".join(cur).strip())
# emit statements separated by a NUL-ish sentinel
print("\x1e".join(x for x in stmts if x))
PY

IFS=$'\x1e' read -r -d '' -a STMTS < /tmp/rti_stmts.txt || true

echo "Deploying $(printf '%s' "${#STMTS[@]}") statements to ${DB}..."
i=0
for stmt in "${STMTS[@]}"; do
  [ -z "${stmt// }" ] && continue
  i=$((i+1))
  label="$(printf '%s' "$stmt" | head -1 | cut -c1-70)"
  body="$(python3 -c 'import json,sys; print(json.dumps({"db":sys.argv[1],"csl":sys.argv[2]}))' "$DB" "$stmt")"
  code=$(curl -s --retry 5 --retry-all-errors --retry-delay 2 -o /tmp/rti_resp.json -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$body" "${CLUSTER_URI}/v1/rest/mgmt" || true)
  if [ "$code" = "200" ]; then
    echo "  [$i] OK   $label"
  else
    echo "  [$i] FAIL($code) $label"
    cat /tmp/rti_resp.json; echo
    exit 1
  fi
done
echo "Done. Verifying tables/functions/views:"
for cmd in ".show tables" ".show functions | project Name" ".show materialized-views | project Name"; do
  body="$(python3 -c 'import json,sys; print(json.dumps({"db":sys.argv[1],"csl":sys.argv[2]}))' "$DB" "$cmd")"
  echo "--- $cmd ---"
  curl -s --retry 5 --retry-all-errors --retry-delay 2 -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "$body" "${CLUSTER_URI}/v1/rest/mgmt" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); [print('  ',r[0]) for r in d['Tables'][0]['Rows']]" 2>/dev/null || true
done
