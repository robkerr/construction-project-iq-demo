#!/usr/bin/env python3
"""Create (or update) the EPC Demo ELT DataPipeline in Microsoft Fabric.

Pattern demonstrated: a *traditional ELT flow* that is neither mirroring nor
shortcuts. It Copies raw Parquet from an Amazon S3 "ods" landing zone into the
lakehouse Files/landing folder, then runs two medallion notebooks:

    S3 (ods/*.parquet)  --Copy-->  Files/landing/  --02_load_bronze-->  bronze.*
                                                    --03_build_silver_gold--> silver/gold

The pipeline is created but NOT run. Trigger it manually in the Fabric portal.

Auth: uses your Azure CLI login (`az account get-access-token`) for the Fabric
REST API. No secrets are stored in this repo.

Usage:
    python create_pipeline.py            # create or update the pipeline
    python create_pipeline.py --verify   # GET the item + definition, print summary
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

WORKSPACE_ID = "8f4cf2c2-381f-4afa-9b7d-9fcfabd4f82d"
PIPELINE_NAME = "PL_ELT_Landing_to_Gold"
PIPELINE_DESC = "Traditional ELT: Copy S3 ods/*.parquet -> lakehouse Files/landing, then run 02_load_bronze and 03_build_silver_gold."
API = "https://api.fabric.microsoft.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFINITION_FILE = os.path.join(HERE, "pipeline-content.json")


def token() -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource",
         "https://api.fabric.microsoft.com", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def request(method: str, url: str, tok: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return resp.status, resp.headers, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, e.headers, (json.loads(raw) if raw else {"error": raw})


def poll_lro(location: str, tok: str):
    """Poll a long-running-operation URL until it terminates."""
    for _ in range(60):
        time.sleep(3)
        status, _, body = request("GET", location, tok)
        state = (body or {}).get("status", "")
        if state in ("Succeeded", "Failed", "Undefined") or status >= 400:
            return state, body
    return "Timeout", {}


def find_pipeline(tok: str) -> str | None:
    status, _, body = request(
        "GET", f"{API}/workspaces/{WORKSPACE_ID}/items?type=DataPipeline", tok)
    for item in (body or {}).get("value", []):
        if item.get("displayName") == PIPELINE_NAME:
            return item.get("id")
    return None


def definition_part() -> dict:
    with open(DEFINITION_FILE, "rb") as f:
        payload = base64.b64encode(f.read()).decode()
    return {
        "parts": [
            {
                "path": "pipeline-content.json",
                "payload": payload,
                "payloadType": "InlineBase64",
            }
        ]
    }


def create_or_update(tok: str):
    existing = find_pipeline(tok)
    definition = definition_part()
    if existing:
        print(f"Pipeline exists ({existing}); updating definition...")
        status, headers, body = request(
            "POST",
            f"{API}/workspaces/{WORKSPACE_ID}/items/{existing}/updateDefinition",
            tok, {"definition": definition})
        item_id = existing
    else:
        print("Creating pipeline...")
        status, headers, body = request(
            "POST", f"{API}/workspaces/{WORKSPACE_ID}/items", tok,
            {"displayName": PIPELINE_NAME, "type": "DataPipeline",
             "description": PIPELINE_DESC, "definition": definition})
        item_id = (body or {}).get("id")

    if status == 202:
        loc = headers.get("Location")
        print(f"Accepted (202); polling {loc}")
        state, lro = poll_lro(loc, tok)
        print(f"LRO terminal state: {state}")
        if state == "Failed":
            print(json.dumps(lro, indent=2))
            sys.exit(1)
        if not item_id:
            item_id = (lro or {}).get("id") or find_pipeline(tok)
    elif status not in (200, 201):
        print(f"ERROR {status}:")
        print(json.dumps(body, indent=2))
        sys.exit(1)

    print(f"OK. Pipeline id: {item_id}")
    return item_id


def verify(tok: str):
    item_id = find_pipeline(tok)
    if not item_id:
        print("Pipeline not found.")
        sys.exit(1)
    status, headers, body = request(
        "POST",
        f"{API}/workspaces/{WORKSPACE_ID}/items/{item_id}/getDefinition", tok)
    if status == 202:
        loc = headers.get("Location")
        state, _ = poll_lro(loc, tok)
        # result is at the operation's /result endpoint
        status, _, body = request("GET", loc + "/result", tok)
    parts = (body or {}).get("definition", {}).get("parts", [])
    print(f"Pipeline id: {item_id}")
    for p in parts:
        if p.get("path") == "pipeline-content.json":
            decoded = base64.b64decode(p["payload"]).decode()
            doc = json.loads(decoded)
            acts = doc.get("properties", {}).get("activities", [])
            print(f"Activities ({len(acts)}):")
            for a in acts:
                deps = [d["activity"] for d in a.get("dependsOn", [])]
                dep = f"  after {deps}" if deps else "  (start)"
                print(f"  - {a['name']} [{a['type']}]{dep}")


def main():
    tok = token()
    if "--verify" in sys.argv:
        verify(tok)
    else:
        create_or_update(tok)
        print("\nVerifying...")
        verify(tok)
        print("\nPipeline created. It has NOT been run. Trigger it manually in Fabric.")


if __name__ == "__main__":
    main()
