#!/usr/bin/env python3
"""EPC Demo - commissioning telemetry producer.

Streams engineered-equipment commissioning telemetry into the Fabric
Eventstream custom-app endpoint (Event Hubs-compatible), which routes it to the
eh_rti_telemetry KQL database, table `commissioning_telemetry`.

Fleet = power transformers / shunt reactors being commissioned at the Project
Falcon (PRJ-001) substation. The hero asset ET-1001 is scripted to drift from
healthy -> warning -> alarm over the run, reproducing the batch emergency work
order WO-900001 live.

The connection string is NEVER stored in the repo. Provide it via env var:

    export ES_CONNECTION_STRING="Endpoint=sb://...;SharedAccessKeyName=...;SharedAccessKey=...;EntityPath=..."
    python produce_telemetry.py --seconds 180

Get the connection string with:  python create_eventstream.py --endpoint
"""
import argparse
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timezone

try:
    from azure.eventhub import EventHubProducerClient, EventData
except ImportError:
    sys.exit("azure-eventhub not installed. Run: ./.venv/bin/pip install azure-eventhub")

# Fleet: (equipment_tag, asset_class, project_id, phase, is_hero)
FLEET = [
    ("ET-1001", "power_transformer", "PRJ-001", "energization",  True),
    ("ET-1002", "power_transformer", "PRJ-001", "energization",  False),
    ("ET-1003", "power_transformer", "PRJ-001", "trial_run",     False),
    ("SR-2001", "shunt_reactor",     "PRJ-001", "energization",  False),
    ("SR-2002", "shunt_reactor",     "PRJ-001", "steady_state",  False),
    ("ET-1101", "power_transformer", "PRJ-002", "trial_run",     False),
    ("ET-1102", "power_transformer", "PRJ-002", "steady_state",  False),
]

# Healthy baselines per asset_class.
BASE = {
    "power_transformer": dict(winding=66.0, oil=56.0, current=485.0, load=76.0,
                              dga=42.0, vib=2.1, tap=7, cooling="ONAF"),
    "shunt_reactor":     dict(winding=61.0, oil=52.0, current=210.0, load=64.0,
                              dga=35.0, vib=1.7, tap=5, cooling="ONAN"),
}


def derive_status(winding, dga, vib):
    if winding >= 95 or dga >= 250 or vib >= 8:
        return "alarm"
    if winding >= 80 or dga >= 150 or vib >= 6:
        return "warning"
    return "ok"


def reading(tag, cls, project, phase, is_hero, progress):
    b = BASE[cls]
    j = random.gauss
    winding = j(b["winding"], 1.2)
    oil = j(b["oil"], 1.0)
    dga = max(0.0, j(b["dga"], 4.0))
    vib = max(0.0, j(b["vib"], 0.25))
    current = max(0.0, j(b["current"], 20.0))
    load = min(100.0, max(0.0, j(b["load"], 3.0)))

    if is_hero:
        # Scripted fault ramp on ET-1001 as commissioning progresses (0.0 -> 1.0).
        winding += 40.0 * progress          # 66 -> ~106
        oil += 22.0 * progress
        dga += 270.0 * progress             # 42 -> ~312
        vib += 6.5 * progress               # 2.1 -> ~8.6
        current += 60.0 * progress
        load = min(100.0, load + 18.0 * progress)

    status = derive_status(winding, dga, vib)
    return {
        "event_time": datetime.now(timezone.utc).isoformat(),
        "equipment_tag": tag,
        "project_id": project,
        "asset_class": cls,
        "commissioning_phase": phase,
        "winding_temp_c": round(winding, 2),
        "top_oil_temp_c": round(oil, 2),
        "load_current_a": round(current, 1),
        "load_pct": round(load, 1),
        "dga_h2_ppm": round(dga, 1),
        "vibration_mm_s": round(vib, 2),
        "ambient_temp_c": round(j(30.0, 1.5), 1),
        "tap_position": int(b["tap"]),
        "cooling_stage": b["cooling"],
        "status": status,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=180, help="run duration")
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between ticks")
    args = ap.parse_args()

    conn = os.environ.get("ES_CONNECTION_STRING")
    if not conn:
        sys.exit("Set ES_CONNECTION_STRING (see create_eventstream.py --endpoint).")

    producer = EventHubProducerClient.from_connection_string(conn)
    start = time.time()
    ticks = max(1, int(args.seconds / args.interval))
    sent = 0
    hero_status_seen = set()
    print(f"Streaming {len(FLEET)} assets for ~{args.seconds}s "
          f"(tick {args.interval}s). ET-1001 will ramp to alarm...")
    try:
        with producer:
            for t in range(ticks):
                progress = t / max(1, ticks - 1)   # 0.0 -> 1.0
                batch = producer.create_batch()
                for tag, cls, project, phase, is_hero in FLEET:
                    ev = reading(tag, cls, project, phase, is_hero, progress)
                    if is_hero and ev["status"] not in hero_status_seen:
                        hero_status_seen.add(ev["status"])
                        print(f"  t={t*args.interval:5.0f}s  ET-1001 -> {ev['status']} "
                              f"(winding {ev['winding_temp_c']}C, H2 {ev['dga_h2_ppm']}ppm)")
                    batch.add(EventData(json.dumps(ev)))
                producer.send_batch(batch)
                sent += len(FLEET)
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    print(f"Done. Sent {sent} events in {time.time()-start:.0f}s.")


if __name__ == "__main__":
    main()
