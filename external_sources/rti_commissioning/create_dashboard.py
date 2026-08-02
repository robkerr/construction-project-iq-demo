#!/usr/bin/env python3
"""Create the EPC Demo commissioning Real-Time Dashboard (KQLDashboard).

Tiles (single page, over commissioning_telemetry in eh_rti_telemetry):
  A. Line  — winding temperature trend by asset (equipment_tag series)
  B. Table — active alarms (active_alarms() KQL function)
  C. Line  — dissolved-gas H2 (ppm) trend by asset

Auth: your Azure CLI login. No secrets stored in the repo.

Usage:
    python create_dashboard.py          # create/update (idempotent)
    python create_dashboard.py --show   # decode & print current definition
"""
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

WORKSPACE_ID = "8f4cf2c2-381f-4afa-9b7d-9fcfabd4f82d"
KQL_DB_ID = "b110a01f-386f-4adb-9249-a8dc9f1062c1"   # == underlying Kusto DatabaseName
CLUSTER_URI = "https://trd-psr494w5ftntwyskww.z3.kusto.fabric.microsoft.com"
DASH_NAME = "rtdCommissioning"
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


def find_dash(tok):
    s, _, b = request("GET", f"{API}/workspaces/{WORKSPACE_ID}/kqlDashboards", tok)
    for i in (b or {}).get("value", []):
        if i.get("displayName") == DASH_NAME:
            return i.get("id")
    return None


def line_options(xcol, ycols, series):
    return {
        "multipleYAxes": {"base": {"id": "-1", "label": "", "columns": [],
                                   "yAxisMaximumValue": None, "yAxisMinimumValue": None,
                                   "yAxisScale": "linear", "horizontalLines": []},
                          "additional": [], "showMultiplePanels": False},
        "hideLegend": False, "legendLocation": "bottom",
        "xColumnTitle": "", "xColumn": xcol, "yColumns": ycols,
        "seriesColumns": series, "xAxisScale": "linear", "verticalLine": "",
        "crossFilterDisabled": False, "drillthroughDisabled": False,
        "crossFilter": [], "drillthrough": [],
    }


def table_options():
    return {"table__enableRenderLinks": True, "colorRulesDisabled": True,
            "crossFilterDisabled": False, "drillthroughDisabled": False,
            "crossFilter": [], "drillthrough": [], "table__renderLinks": [],
            "colorRules": []}


def dashboard_json():
    ds_id = str(uuid.uuid4())
    page_id = str(uuid.uuid4())
    q_wind, q_alarm, q_dga = (str(uuid.uuid4()) for _ in range(3))

    data_source = {
        "kind": "kusto-trident",
        "scopeId": "kusto-trident",
        "clusterUri": CLUSTER_URI,
        "name": "eh_rti_telemetry",
        "database": KQL_DB_ID,
        "workspace": WORKSPACE_ID,
        "id": ds_id,
    }

    def q(qid, text):
        return {"dataSource": {"kind": "inline", "dataSourceId": ds_id},
                "text": text, "id": qid, "usedVariables": []}

    queries = [
        q(q_wind, "commissioning_telemetry\n"
                  "| summarize winding_temp_c=round(avg(winding_temp_c),1) "
                  "by bin(event_time, 15s), equipment_tag\n| order by event_time asc"),
        q(q_alarm, "active_alarms()"),
        q(q_dga, "commissioning_telemetry\n"
                 "| summarize dga_h2_ppm=round(avg(dga_h2_ppm),1) "
                 "by bin(event_time, 15s), equipment_tag\n| order by event_time asc"),
    ]

    def tile(title, vt, x, y, w, h, qid, opts):
        return {"id": str(uuid.uuid4()), "title": title, "visualType": vt,
                "pageId": page_id, "layout": {"x": x, "y": y, "width": w, "height": h},
                "queryRef": {"kind": "query", "queryId": qid}, "visualOptions": opts}

    tiles = [
        tile("Winding temperature by asset (°C)", "line", 0, 0, 16, 9, q_wind,
             line_options("event_time", ["winding_temp_c"], ["equipment_tag"])),
        tile("Active alarms", "table", 16, 0, 8, 9, q_alarm, table_options()),
        tile("Dissolved-gas H₂ by asset (ppm)", "line", 0, 9, 16, 8, q_dga,
             line_options("event_time", ["dga_h2_ppm"], ["equipment_tag"])),
    ]

    return {
        "$schema": "https://pbiadx.powerbi.com/static/d/schema/60/dashboard.json",
        "schema_version": "60",
        "title": "EPC Commissioning Telemetry",
        "autoRefresh": {"enabled": True, "defaultInterval": "30s"},
        "baseQueries": [],
        "dataSources": [data_source],
        "pages": [{"name": "Commissioning", "id": page_id}],
        "parameters": [{
            "kind": "duration", "id": str(uuid.uuid4()),
            "displayName": "Time range", "description": "",
            "beginVariableName": "_startTime", "endVariableName": "_endTime",
            "defaultValue": {"kind": "dynamic", "count": 1, "unit": "days"},
            "showOnPages": {"kind": "all"},
        }],
        "queries": queries,
        "tiles": tiles,
        "embeddedApps": [],
    }


def platform_part():
    plat = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "KQLDashboard", "displayName": DASH_NAME},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid4())},
    }
    return base64.b64encode(json.dumps(plat).encode()).decode()


def create_or_update(tok):
    dash_b64 = base64.b64encode(json.dumps(dashboard_json()).encode()).decode()
    parts = [{"path": "RealTimeDashboard.json", "payload": dash_b64,
              "payloadType": "InlineBase64"}]
    existing = find_dash(tok)
    if existing:
        body = {"definition": {"parts": parts}}
        url = f"{API}/workspaces/{WORKSPACE_ID}/kqlDashboards/{existing}/updateDefinition"
        s, h, b = request("POST", url, tok, body)
        if s == 202:
            st, lro = poll(h.get("Location"), tok)
            print(f"updateDefinition LRO: {st}")
            if st == "Failed":
                print(json.dumps(lro, indent=2)); sys.exit(1)
        elif s in (200, 201):
            print("updateDefinition: OK")
        else:
            print(f"ERROR {s}: {json.dumps(b, indent=2)}"); sys.exit(1)
        print(f"Dashboard '{DASH_NAME}' updated: {existing}")
        return existing

    body = {"displayName": DASH_NAME,
            "description": "RTI: live commissioning telemetry dashboard.",
            "definition": {"parts": parts}}
    s, h, b = request("POST", f"{API}/workspaces/{WORKSPACE_ID}/kqlDashboards", tok, body)
    item_id = (b or {}).get("id")
    if s == 202:
        st, lro = poll(h.get("Location"), tok)
        print(f"Create LRO: {st}")
        if st == "Failed":
            print(json.dumps(lro, indent=2)); sys.exit(1)
        item_id = item_id or (lro or {}).get("id") or find_dash(tok)
    elif s not in (200, 201):
        print(f"ERROR {s}: {json.dumps(b, indent=2)}"); sys.exit(1)
    print(f"Dashboard '{DASH_NAME}' created: {item_id}")
    return item_id


def show(tok):
    rid = find_dash(tok)
    if not rid:
        print(f"No dashboard named {DASH_NAME}"); return
    url = f"{API}/workspaces/{WORKSPACE_ID}/kqlDashboards/{rid}/getDefinition"
    s, h, b = request("POST", url, tok, {})
    if s == 202:
        _, b = poll(h.get("Location"), tok)
    for part in (b or {}).get("definition", {}).get("parts", []):
        if part.get("path") == "RealTimeDashboard.json":
            print(json.dumps(json.loads(base64.b64decode(part["payload"]).decode()), indent=2))
            return
    print(json.dumps(b, indent=2))


def main():
    tok = token()
    if "--show" in sys.argv:
        show(tok); return
    create_or_update(tok)


if __name__ == "__main__":
    main()
