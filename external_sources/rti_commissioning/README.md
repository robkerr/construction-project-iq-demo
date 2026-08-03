# RTI: Commissioning Telemetry (Eventstream → KQL Database)

The fourth ingestion pattern in the demo — **Real-Time Intelligence**. Neither
mirroring, shortcuts, nor batch ELT: this is a live **event stream** landing in
a **KQL database** (Eventhouse) for sub-minute telemetry analytics.

```
produce_telemetry.py (WSL)
    │  Event Hubs-compatible custom-app endpoint
    ▼
Eventstream  "esCommissioning"  (CustomEndpoint source)
    │  ProcessedIngestion (pass-through)
    ▼
Eventhouse  "eh_rti_telemetry"  ▶  KQL DB  ▶  table commissioning_telemetry
    │
    ├─ materialized view  latest_by_asset      (current state per asset)
    ├─ function  winding_temp_anomalies()      (series_decompose_anomalies)
    ├─ function  dga_trend()                    (dissolved-gas trend)
    └─ function  active_alarms()                (drives Activator / dashboard)
```

## The scenario

Power transformers and shunt reactors being **commissioned/energized** at the
Project **Falcon (PRJ-001)** substation stream per-tick telemetry: winding &
oil temperature, load current, dissolved-hydrogen (DGA), and vibration. The
hero asset **ET-1001** is scripted to drift from healthy → warning → **alarm**
during the run — reproducing the batch emergency work order **WO-900001** live,
so the RTI stream fuses with the mirrored/shortcut/ELT data on `equipment_tag`
and `project_id`.

## Fabric objects (already provisioned in workspace `8f4cf2c2-…`)

| Object | Type | ID |
|--------|------|----|
| `eh_rti_telemetry` | Eventhouse | `3800b0b8-c465-4a80-bdce-27f7fb5ea6f6` |
| `eh_rti_telemetry` | KQL Database | `b110a01f-386f-4adb-9249-a8dc9f1062c1` |
| `esCommissioning` | Eventstream | `60df0ca6-45ea-4cad-a04f-3101f5135dbb` |
| `actCommissioningAlarms` | Activator (Reflex) | `f1a0359f-44a0-4af1-998d-e42934f019a5` |
| `rtdCommissioning` | Real-Time Dashboard | `0912dc5b-e3fa-4b8f-880a-c8bd1bb137b3` |

KQL cluster URI: `https://trd-psr494w5ftntwyskww.z3.kusto.fabric.microsoft.com`

## Files

| File | Purpose |
|------|---------|
| `kql/schema.kql` | Table, JSON mapping, streaming-ingestion + retention/caching policies, materialized view, 3 RTI functions. |
| `deploy_kql.sh` | Deploys `schema.kql` statement-by-statement (Kusto mgmt REST, Entra auth). Idempotent. |
| `create_eventstream.py` | Creates `esCommissioning` (CustomEndpoint → KQL DB, ProcessedIngestion) and prints the producer connection string. `--endpoint` re-prints it. |
| `produce_telemetry.py` | Streams the fleet to the custom-app endpoint; ET-1001 ramps to alarm. |
| `create_activator.py` | Creates Activator (Reflex) `actCommissioningAlarms` — emails when an asset's `status` **changes to `alarm`**. `--show` decodes the rule. |
| `create_dashboard.py` | Creates Real-Time Dashboard `rtdCommissioning` (winding-temp & DGA line tiles + `active_alarms()` table). `--show` decodes it. |

## Security

- **No secrets in the repo.** The Eventstream custom-app endpoint vends an
  Event Hubs-compatible SAS connection string (a *Fabric-managed* key, not an
  Azure Storage account key). Retrieve it at runtime and pass it via the
  `ES_CONNECTION_STRING` env var; `*.endpoint`/`.env` are git-ignored.
- All provisioning (`az`/REST) uses your Entra login.

## Build & run

```bash
# 1. Deploy the KQL schema
./deploy_kql.sh

# 2. Create the Eventstream (idempotent) and print the endpoint
./../../.venv/bin/python create_eventstream.py

# 3. Stream a burst (connection string kept out of shell history/logs)
export ES_CONNECTION_STRING="$(./../../.venv/bin/python create_eventstream.py --endpoint \
  | ./../../.venv/bin/python -c 'import sys,json; s=sys.stdin.read(); print(json.loads(s[s.find(chr(123)):])["accessKeys"]["primaryConnectionString"])')"
./../../.venv/bin/python produce_telemetry.py --seconds 180 --interval 2
```

## Verify (KQL)

```kql
commissioning_telemetry | summarize count() by equipment_tag, status
latest_by_asset | where equipment_tag == 'ET-1001'
active_alarms()
winding_temp_anomalies(15m, 10s)
dga_trend(24h)
```

## Alerting & visualization (built)

**Activator `actCommissioningAlarms`** (`create_activator.py`) — a KQL-sourced
`EventTrigger` Reflex over `commissioning_telemetry`. It fires when an asset's
`status` **changes to `alarm`** (transition-based, so each asset notifies once
when it *enters* alarm rather than on every hot sample) and sends an
**email** naming the `equipment_tag` and `project_id`. The rule is created in
the running state (`shouldRun: true`).

**Real-Time Dashboard `rtdCommissioning`** (`create_dashboard.py`) — one page,
three tiles over the same table/functions:

| Tile | Visual | Query |
|------|--------|-------|
| Winding temperature by asset (°C) | line | `winding_temp_c` avg by 15s bin, series = `equipment_tag` |
| Active alarms | table | `active_alarms()` |
| Dissolved-gas H₂ by asset (ppm) | line | `dga_h2_ppm` avg by 15s bin, series = `equipment_tag` |

```bash
./../../.venv/bin/python create_activator.py     # create/verify the alert
./../../.venv/bin/python create_dashboard.py      # create/verify the dashboard
```

> The producer stamps `event_time` with simulated commissioning timestamps, so
> the dashboard tiles query the full table rather than the "last hour" picker.
> Run a fresh `produce_telemetry.py` burst to watch ET-1001 ramp live and the
> Activator email fire.

## Demo run (recommended) & troubleshooting

For a live demo, use the helper — it auto-resumes a paused destination first,
then streams:

```bash
./run_demo_burst.sh 180          # let it run to COMPLETION; do NOT Ctrl-C early
```

- ET-1001 ramps `ok → warning → alarm`; **alarm starts at ~72% of the run**
  (~130s into a 180s run). Shorter run = earlier alarm (`./run_demo_burst.sh 90`).
- After the alarm, the **email lands ~2–4 min later** (Activator polls every 60s
  with a 60s ingestion delay, plus mail delivery). Check Junk/Other too.

**No alarm email? Check the Eventstream destination first.** The most common
cause is a **paused Eventhouse destination**: telemetry enters the Eventstream
(source shows `Running`) but never lands in `commissioning_telemetry`, so the
Activator sees nothing and never fires. Diagnose / fix:

```bash
# Auto-resume any paused source/destination (also runs inside run_demo_burst.sh)
./../../.venv/bin/python create_eventstream.py --ensure-running

# Confirm fresh rows are landing (secs_since_latest should be small)
#   commissioning_telemetry
#   | summarize latest=max(event_time),
#               secs=datetime_diff('second', now(), max(event_time))
```

If `--ensure-running` reports it resumed the `KqlCommissioning` destination,
re-run the burst — data will flow and the alarm email will fire.

