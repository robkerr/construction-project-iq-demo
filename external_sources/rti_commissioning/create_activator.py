#!/usr/bin/env python3
"""Create the EPC Demo commissioning-telemetry Activator (Reflex).

Alerting story:
    KQL source (commissioning_telemetry in eh_rti_telemetry)
        -> SourceEvent
           -> EventTrigger rule: fire when an asset's `status` CHANGES TO "alarm"
              -> EmailMessage action to the on-call recipient

Transition-based (ChangesTo) so each asset notifies once when it *enters*
alarm, rather than emailing on every alarm sample while it stays hot.

Auth: your Azure CLI login. No secrets stored in the repo.

Usage:
    python create_activator.py            # create (idempotent) + author rule
    python create_activator.py --show     # decode & print the current definition
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
KQL_DB_ID = "b110a01f-386f-4adb-9249-a8dc9f1062c1"
TABLE = "commissioning_telemetry"
REFLEX_NAME = "actCommissioningAlarms"
ALERT_EMAIL = "robkerr@MngEnvMCAP969131.onmicrosoft.com"
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


def find_reflex(tok):
    s, _, b = request("GET", f"{API}/workspaces/{WORKSPACE_ID}/reflexes", tok)
    for i in (b or {}).get("value", []):
        if i.get("displayName") == REFLEX_NAME:
            return i.get("id")
    return None


def create_reflex(tok):
    existing = find_reflex(tok)
    if existing:
        print(f"Reflex '{REFLEX_NAME}' already exists ({existing}); reusing it.")
        return existing
    body = {
        "displayName": REFLEX_NAME,
        "description": "RTI: alerts when a commissioning asset enters alarm status.",
    }
    s, h, b = request("POST", f"{API}/workspaces/{WORKSPACE_ID}/reflexes", tok, body)
    item_id = (b or {}).get("id")
    if s == 202:
        st, lro = poll(h.get("Location"), tok)
        print(f"Create LRO: {st}")
        if st == "Failed":
            print(json.dumps(lro, indent=2)); sys.exit(1)
        item_id = item_id or (lro or {}).get("id") or find_reflex(tok)
    elif s not in (200, 201):
        print(f"ERROR {s}: {json.dumps(b, indent=2)}"); sys.exit(1)
    print(f"Reflex created: {item_id}")
    return item_id


def kql_query() -> str:
    return (
        "declare query_parameters(startTime:datetime, endTime:datetime);\n"
        f"{TABLE}\n"
        "| where event_time between (startTime .. endTime)\n"
        "| project event_time, equipment_tag, project_id, asset_class, "
        "commissioning_phase, winding_temp_c, top_oil_temp_c, dga_h2_ppm, "
        "vibration_mm_s, status"
    )


def build_entities() -> list:
    container_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    source_event_id = str(uuid.uuid4())
    rule_id = str(uuid.uuid4())

    container = {
        "uniqueIdentifier": container_id,
        "payload": {"name": "Commissioning telemetry", "type": "kqlQueries"},
        "type": "container-v1",
    }

    source = {
        "uniqueIdentifier": source_id,
        "payload": {
            "name": "Commissioning telemetry query",
            "runSettings": {"executionIntervalInSeconds": 60},
            "query": {"queryString": kql_query()},
            "eventhouseItem": {
                "itemId": KQL_DB_ID,
                "workspaceId": WORKSPACE_ID,
                "itemType": "KustoDatabase",
            },
            "queryParameters": [
                {"name": "startTime", "type": "DURATION_START",
                 "value": "2025-01-01T00:00:00Z"},
                {"name": "endTime", "type": "DURATION_END",
                 "value": "2025-01-01T00:05:00Z"},
            ],
            "eventTimeSettings": {
                "timeFieldName": "event_time",
                "ingestionDelayInSeconds": 60,
                "timeZone": "UTC",
            },
            "metadata": {
                "workspaceId": WORKSPACE_ID,
                "measureName": "",
                "querySetId": "",
                "queryId": "",
            },
            "parentContainer": {"targetUniqueIdentifier": container_id},
        },
        "type": "kqlSource-v1",
    }

    source_event_template = {
        "templateId": "SourceEvent",
        "templateVersion": "1.2.4",
        "steps": [{
            "name": "SourceEventStep",
            "id": str(uuid.uuid4()),
            "rows": [{
                "name": "SourceSelector",
                "kind": "SourceReference",
                "arguments": [{"name": "entityId", "type": "string", "value": source_id}],
            }],
        }],
    }
    source_event = {
        "uniqueIdentifier": source_event_id,
        "payload": {
            "name": "Commissioning events",
            "parentContainer": {"targetUniqueIdentifier": container_id},
            "definition": {
                "type": "Event",
                "instance": json.dumps(source_event_template, separators=(",", ":")),
            },
        },
        "type": "timeSeriesView-v1",
    }

    rule_template = {
        "templateId": "EventTrigger",
        "templateVersion": "1.2.4",
        "steps": [
            {
                "name": "FieldsDefaultsStep",
                "id": str(uuid.uuid4()),
                "rows": [{
                    "name": "EventSelector",
                    "kind": "Event",
                    "arguments": [{
                        "name": "event",
                        "kind": "EventReference",
                        "type": "complex",
                        "arguments": [{"name": "entityId", "type": "string",
                                       "value": source_event_id}],
                    }],
                }],
            },
            {
                "name": "EventDetectStep",
                "id": str(uuid.uuid4()),
                "rows": [
                    {"name": "EventFieldSelector", "kind": "EventField",
                     "arguments": [{"name": "fieldName", "type": "string",
                                    "value": "status"}]},
                    {"name": "TextChanges", "kind": "TextChanges",
                     "arguments": [
                         {"name": "op", "type": "string", "value": "ChangesTo"},
                         {"name": "value", "type": "string", "value": "alarm"},
                     ]},
                ],
            },
            {
                "name": "ActStep",
                "id": str(uuid.uuid4()),
                "rows": [{
                    "name": "EmailBinding",
                    "kind": "EmailMessage",
                    "arguments": [
                        {"name": "messageLocale", "type": "string", "value": "en-us"},
                        {"name": "sentTo", "type": "array", "values": [
                            {"type": "string", "value": ALERT_EMAIL}]},
                        {"name": "copyTo", "type": "array", "values": []},
                        {"name": "bCCTo", "type": "array", "values": []},
                        {"name": "subject", "type": "array", "values": [
                            {"type": "string",
                             "value": "EPC Demo ALARM: commissioning asset entered alarm"}]},
                        {"name": "headline", "type": "array", "values": [
                            {"type": "string",
                             "value": "A commissioning asset has entered ALARM status."},
                            {"kind": "EventFieldReference", "type": "complex",
                             "arguments": [{"name": "fieldName", "type": "string",
                                            "value": "equipment_tag"}]},
                        ]},
                        {"name": "optionalMessage", "type": "array", "values": [
                            {"type": "string",
                             "value": ("Winding temperature / DGA H2 / vibration crossed "
                                       "commissioning alarm thresholds. Review the "
                                       "real-time dashboard and dispatch on-call. Asset: ")},
                            {"kind": "EventFieldReference", "type": "complex",
                             "arguments": [{"name": "fieldName", "type": "string",
                                            "value": "equipment_tag"}]},
                            {"type": "string", "value": " on project "},
                            {"kind": "EventFieldReference", "type": "complex",
                             "arguments": [{"name": "fieldName", "type": "string",
                                            "value": "project_id"}]},
                            {"type": "string", "value": "."},
                        ]},
                        {"name": "additionalInformation", "type": "array", "values": []},
                    ],
                }],
            },
        ],
    }
    rule = {
        "uniqueIdentifier": rule_id,
        "payload": {
            "name": "Asset enters alarm",
            "description": "Created by: skills-for-fabric",
            "parentContainer": {"targetUniqueIdentifier": container_id},
            "definition": {
                "type": "Rule",
                "instance": json.dumps(rule_template, separators=(",", ":")),
                "settings": {"shouldRun": True, "shouldApplyRuleOnUpdate": False},
            },
        },
        "type": "timeSeriesView-v1",
    }

    return [container, source, source_event, rule]


def preflight(entities):
    ids = {e["uniqueIdentifier"] for e in entities}
    refs = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("targetUniqueIdentifier",) and isinstance(v, str):
                    refs.append(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(entities)
    # instance strings hold entityId references
    for e in entities:
        inst = e.get("payload", {}).get("definition", {}).get("instance")
        if isinstance(inst, str):
            try:
                obj = json.loads(inst)
            except Exception:
                continue
            def walk2(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        if k == "value" and o.get("name") == "entityId":
                            refs.append(v)
                        walk2(v)
                elif isinstance(o, list):
                    for v in o:
                        walk2(v)
            walk2(obj)
    missing = [r for r in refs if r not in ids]
    if missing:
        print("PREFLIGHT FAILED — unresolved references:", missing)
        sys.exit(1)
    print(f"Preflight OK: {len(entities)} entities, all references resolve.")


def update_definition(tok, reflex_id, entities):
    payload_b64 = base64.b64encode(json.dumps(entities).encode()).decode()
    body = {"definition": {"parts": [
        {"path": "ReflexEntities.json", "payload": payload_b64,
         "payloadType": "InlineBase64"}]}}
    url = f"{API}/workspaces/{WORKSPACE_ID}/reflexes/{reflex_id}/updateDefinition"
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


def show(tok, reflex_id):
    url = f"{API}/workspaces/{WORKSPACE_ID}/reflexes/{reflex_id}/getDefinition"
    s, h, b = request("POST", url, tok, {})
    if s == 202:
        st, b = poll(h.get("Location"), tok)
        # LRO result body may need a follow-up GET on Location result
    for part in (b or {}).get("definition", {}).get("parts", []):
        if part.get("path") == "ReflexEntities.json":
            ents = json.loads(base64.b64decode(part["payload"]).decode())
            print(json.dumps(ents, indent=2))
            return
    print(json.dumps(b, indent=2))


def main():
    tok = token()
    if "--show" in sys.argv:
        rid = find_reflex(tok)
        if not rid:
            print(f"No reflex named {REFLEX_NAME}"); sys.exit(1)
        show(tok, rid)
        return
    reflex_id = create_reflex(tok)
    entities = build_entities()
    preflight(entities)
    update_definition(tok, reflex_id, entities)
    print(f"\nActivator '{REFLEX_NAME}' ready: {reflex_id}")
    print(f"Alert -> email {ALERT_EMAIL} when any asset status ChangesTo 'alarm'.")


if __name__ == "__main__":
    main()
