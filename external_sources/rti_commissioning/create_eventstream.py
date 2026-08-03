#!/usr/bin/env python3
"""Create the EPC Demo commissioning-telemetry Eventstream and print the
custom-app (Event Hubs-compatible) connection string the producer uses.

Topology:
    CommissioningApp (CustomEndpoint source)
        -> esCommissioning-stream (DefaultStream)
        -> KqlCommissioning (Eventhouse dest, ProcessedIngestion)
           -> KQL DB eh_rti_telemetry, table commissioning_telemetry

Auth: your Azure CLI login. No secrets stored in the repo.

Usage:
    python create_eventstream.py            # create (idempotent) + print endpoint
    python create_eventstream.py --endpoint # just re-print the source connection
"""
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

WORKSPACE_ID = "8f4cf2c2-381f-4afa-9b7d-9fcfabd4f82d"
KQL_DB_ID = "b110a01f-386f-4adb-9249-a8dc9f1062c1"
KQL_DB_NAME = "eh_rti_telemetry"
TABLE = "commissioning_telemetry"
ES_NAME = "esCommissioning"
API = "https://api.fabric.microsoft.com/v1"


def token() -> str:
    out = subprocess.run(
        ["az", "account", "get-access-token", "--resource",
         "https://api.fabric.microsoft.com", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()


def request(method, url, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            return r.status, r.headers, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, e.headers, (json.loads(raw) if raw else {"error": raw})


def poll(location, tok):
    for _ in range(60):
        time.sleep(3)
        s, _, b = request("GET", location, tok)
        st = (b or {}).get("status", "")
        if st in ("Succeeded", "Failed", "Undefined") or s >= 400:
            return st, b
    return "Timeout", {}


def topology() -> dict:
    return {
        "compatibilityLevel": "1.0",
        "sources": [
            {"name": "CommissioningApp", "type": "CustomEndpoint", "properties": {}}
        ],
        "streams": [
            {"name": f"{ES_NAME}-stream", "type": "DefaultStream", "properties": {},
             "inputNodes": [{"name": "CommissioningApp"}]}
        ],
        "operators": [],
        "destinations": [
            {"name": "KqlCommissioning", "type": "Eventhouse",
             "properties": {
                 "dataIngestionMode": "ProcessedIngestion",
                 "workspaceId": WORKSPACE_ID,
                 "itemId": KQL_DB_ID,
                 "databaseName": KQL_DB_NAME,
                 "tableName": TABLE,
                 "inputSerialization": {"type": "Json", "properties": {"encoding": "UTF8"}},
             },
             "inputNodes": [{"name": f"{ES_NAME}-stream"}]}
        ],
    }


def find_es(tok):
    s, _, b = request("GET", f"{API}/workspaces/{WORKSPACE_ID}/eventstreams", tok)
    for i in (b or {}).get("value", []):
        if i.get("displayName") == ES_NAME:
            return i.get("id")
    return None


def create(tok):
    if find_es(tok):
        print(f"Eventstream '{ES_NAME}' already exists ({find_es(tok)}); leaving as-is.")
        return find_es(tok)
    top_b64 = base64.b64encode(json.dumps(topology()).encode()).decode()
    props_b64 = base64.b64encode(json.dumps(
        {"retentionTimeInDays": 1, "eventThroughputLevel": "Low"}).encode()).decode()
    body = {
        "displayName": ES_NAME,
        "type": "Eventstream",
        "description": "RTI: commissioning telemetry custom-app source -> KQL DB.",
        "definition": {"parts": [
            {"path": "eventstream.json", "payload": top_b64, "payloadType": "InlineBase64"},
            {"path": "eventstreamProperties.json", "payload": props_b64, "payloadType": "InlineBase64"},
        ]},
    }
    s, h, b = request("POST", f"{API}/workspaces/{WORKSPACE_ID}/items", tok, body)
    item_id = (b or {}).get("id")
    if s == 202:
        st, lro = poll(h.get("Location"), tok)
        print(f"Create LRO: {st}")
        if st == "Failed":
            print(json.dumps(lro, indent=2)); sys.exit(1)
        item_id = item_id or (lro or {}).get("id") or find_es(tok)
    elif s not in (200, 201):
        print(f"ERROR {s}: {json.dumps(b, indent=2)}"); sys.exit(1)
    print(f"Eventstream created: {item_id}")
    return item_id


def ensure_running(tok, es_id, wait=True):
    """Resume any Paused/Stopped source or destination so telemetry reaches the
    Eventhouse. A paused Eventhouse destination silently drops the stream: events
    enter the Eventstream but never land in the KQL table, so no alarm fires."""
    s, _, topo = request("GET", f"{API}/workspaces/{WORKSPACE_ID}/eventstreams/{es_id}/topology", tok)
    if s >= 400 or not topo:
        print("Preflight: could not read Eventstream topology; skipping resume.",
              file=sys.stderr)
        return
    resumed = []
    for kind in ("sources", "destinations"):
        for node in (topo.get(kind) or []):
            st = (node.get("status") or "")
            if st.lower() in ("paused", "stopped"):
                nid, nm = node.get("id"), node.get("name")
                rs, _, _ = request(
                    "POST",
                    f"{API}/workspaces/{WORKSPACE_ID}/eventstreams/{es_id}/{kind}/{nid}/resume",
                    tok, {"startType": "Now"})
                print(f"Preflight: resuming {kind[:-1]} '{nm}' (was {st}) -> HTTP {rs}",
                      file=sys.stderr)
                resumed.append((kind, nid, nm))
    if not resumed:
        print("Preflight: all Eventstream nodes already running.", file=sys.stderr)
        return
    if wait:
        want = {(k, i) for k, i, _ in resumed}
        for _ in range(15):  # up to ~45s for Resuming -> Running
            time.sleep(3)
            _, _, t2 = request("GET",
                               f"{API}/workspaces/{WORKSPACE_ID}/eventstreams/{es_id}/topology", tok)
            running = {(k, n.get("id")) for k in ("sources", "destinations")
                       for n in (t2.get(k) or []) if (n.get("status") or "").lower() == "running"}
            if want <= running:
                print("Preflight: resumed nodes are Running.", file=sys.stderr)
                return
        print("Preflight: resume issued; nodes still transitioning (continuing).",
              file=sys.stderr)


def print_endpoint(tok, es_id):
    # Topology API: find the source id, then GET its connection.
    s, _, topo = request("GET", f"{API}/workspaces/{WORKSPACE_ID}/eventstreams/{es_id}/topology", tok)
    src_id = None
    for src in (topo or {}).get("sources", []):
        if src.get("name") == "CommissioningApp":
            src_id = src.get("id")
    if not src_id:
        print("Could not resolve source id from topology:", json.dumps(topo, indent=2)[:500]); return
    s, _, conn = request(
        "GET",
        f"{API}/workspaces/{WORKSPACE_ID}/eventstreams/{es_id}/sources/{src_id}/connection", tok)
    print("\n=== Custom-app source connection (feed the producer) ===")
    print(json.dumps(conn, indent=2))


def main():
    tok = token()
    if "--ensure-running" in sys.argv:
        es_id = find_es(tok)
        if es_id:
            ensure_running(tok, es_id)
        else:
            print("No esCommissioning eventstream found.", file=sys.stderr)
        return
    es_id = find_es(tok) if "--endpoint" in sys.argv else create(tok)
    if not es_id:
        es_id = find_es(tok)
    ensure_running(tok, es_id)
    print_endpoint(tok, es_id)


if __name__ == "__main__":
    main()
