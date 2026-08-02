# Project Controls IQ — Fabric IQ Ontology Design

A build-along specification for the **Fabric IQ Ontology** (preview) that sits on
top of the OneLake `silver`/`gold` lakehouse tables **and** the Real-Time
Intelligence (RTI) Eventhouse. It is the shared **semantic backbone** the demo
flow keeps promising: model the business entities and their relationships *once*
so Power BI, Data Agents, and the operations/Activator layer all speak the same
language.

> This document is written so you can **configure the ontology by hand in the
> Fabric portal**. Each entity type lists its source table, its key, and every
> property → source-column mapping. Relationships list the exact **link table**
> and the two key columns to bind. Follow the sections in order.

---

## 1. What the ontology has to cover (the three pillars)

| Pillar | Use case | Entities that carry it |
|---|---|---|
| **Analytics** | Portfolio schedule risk → **MPR** (Maya) | Project, WorkPackage, PurchaseOrder, Supplier, EngineeringChange |
| **Real-time** | Commissioning telemetry → **alarm** (Daniel) | **Equipment** (static + time-series), WorkOrder |
| **AI / agents** | Bid evaluation **TBE→CBE**, grounded Q&A | RFQ, Bid, Supplier, Equipment, Project |
| *Cross-cutting* | Permits & inspections context | Permit |

The ontology's real job is to make the **hero thread** a single connected graph,
so an agent or a graph-walk can traverse from *one supplier* to the *late PO*,
the *disqualified bid*, and the *alarming asset* — the payoff no single source
system can produce.

### The hero-thread graph (what "good" looks like)

```
                         ┌───────────────────────────┐
                         │  Supplier  (high-risk)     │
                         └─────┬───────────────┬──────┘
                     fulfills  │               │  submits
                               ▼               ▼
   Project ──contains──► WorkPackage      Bid (disqualified,
  (Falcon/  │  procuredVia │  (WBS)        cheapest) ──receivesBid⁻¹──► RFQ-0001
  PRJ-001)  │              ▼                                              │
     │ hasAsset      PurchaseOrder                                        │ forEquipment
     │              (PO-00512, late)                                      ▼
     ▼                                                              Equipment
  Equipment ◄───────────────────────── scopes ───────────────────  (ET-1001)
 (ET-1001) ──hasWorkOrder──► WorkOrder (WO-900001)                       │
     │                                                                   │ time-series
     └────────── commissioning_telemetry (Eventhouse) ◄──────────────────┘
```

One `Supplier` node touches cost (PO), procurement (Bid/RFQ), and the field
(Equipment telemetry + WorkOrder). That traversal *is* the demo.

---

## 2. Prerequisites — get the sources "ontology-ready" first

Fabric IQ Ontology bindings have hard rules. Check these **before** you start
clicking, or bindings will silently fail or be unavailable.

1. **Lakehouse static bindings must be MANAGED tables** in the same lakehouse.
   External tables and **shortcuts are not supported**, and a lakehouse with
   **OneLake security enabled cannot be a source**.
2. **No Delta column-mapping** on the source table (auto-enabled if column names
   contain spaces or any of `,;{}()=\n\t`, or if the table backs an import-mode
   semantic model). Our `silver`/`gold` columns are clean snake_case — good.
3. **Static binding before time-series binding** — an entity type's time-series
   binding needs its key property already populated by the static binding.
4. Eventhouse (Kusto) tables can only be bound as **time-series**, never static.

### Source-readiness map

| Entity source | Where it lives today | Managed table? | Action needed |
|---|---|---|---|
| `gold.project_schedule_risk` | Lakehouse gold (managed) | ✅ | none |
| `silver.dim_wbs` | Lakehouse silver (managed) | ✅ | none |
| `silver.sap_supplier` | Lakehouse silver (managed) | ✅ | none |
| `silver.sap_mm_po` | Lakehouse silver (managed) | ✅ | none |
| `silver.dim_rfq` | Lakehouse silver (managed) | ✅ | none |
| `gold.bid_evaluation` | Lakehouse gold (managed) | ✅ | none |
| `silver.fact_engineering_change` | Lakehouse silver (managed) | ✅ | none |
| **Equipment asset** attrs | BigQuery **mirror** → bronze shortcut | ❌ shortcut | **materialize** `silver.dim_equipment` (SQL below) |
| **Work orders** | BigQuery **mirror** → bronze shortcut | ❌ shortcut | **materialize** `silver.fact_work_order` (SQL below) |
| **Permits** | S3 Delta **shortcut** → bronze | ❌ shortcut | **materialize** `silver.dim_permit` (SQL below) |
| `commissioning_telemetry` | Eventhouse `eh_rti_telemetry` | ✅ (Kusto, TS only) | none |

> **Why materialize?** Ontology static bindings reject shortcuts/mirrors. Add a
> one-time notebook cell (or step in `03_build_silver_gold`) that CTAS-copies the
> three shortcut sources into managed `silver` tables. Cheap, and it also gives
> the ontology a stable schema even if the mirror re-syncs.

> **⚠ Confirm the bronze source names first.** The BigQuery and S3 data land as
> **shortcuts** whose bronze table names depend on how you wired them (per
> `external_sources/README.md`, BigQuery work-order tables appear as `wo_*`, and
> the S3 permit shortcut exposes the six `permits/*` Delta tables). Adjust the
> `FROM` clauses below to match the actual shortcut table names in your bronze
> lakehouse before running.

```sql
-- Run once in the lakehouse (e.g., append to 03_build_silver_gold).
-- Replace bronze.<name> with your actual bronze shortcut/mirror table names.
CREATE OR REPLACE TABLE silver.dim_equipment USING delta AS
SELECT asset_id, equipment_tag, project_id, wbs_id, asset_class, manufacturer,
       model_no, criticality, install_date, operational_status
FROM   bronze.equipment_asset;              -- BigQuery-mirrored shortcut

CREATE OR REPLACE TABLE silver.fact_work_order USING delta AS
SELECT wo_id, equipment_tag, project_id, wbs_id, asset_id, wo_type, priority,
       status AS wo_status, reported_date, scheduled_date, completed_date,
       estimated_hours, actual_hours
FROM   bronze.work_order;                    -- BigQuery-mirrored shortcut

CREATE OR REPLACE TABLE silver.dim_permit USING delta AS
SELECT permit_id, project_id, authority_id, permit_type,
       status AS permit_status, applied_date, issued_date, expiry_date,
       valuation_usd
FROM   bronze.permit;                        -- S3 Delta shortcut
```

### Collect these IDs before configuring (you'll paste them into each binding)

- **Workspace ID** (`workspaceId`) of the lakehouse workspace.
- **Lakehouse item ID** (`itemId` / ArtifactId) that holds `silver`/`gold`.
- **Eventhouse KQL DB** `clusterUri` + `databaseName` — from the demo dashboard:
  `clusterUri = https://trd-psr494w5ftntwyskww.z3.kusto.fabric.microsoft.com`,
  `database = eh_rti_telemetry` (the RTI dashboard JSON shows the same cluster).
- Eventhouse **item ID** (KustoDatabase ArtifactId).

---

## 3. Naming & value-type conventions (read once, saves pain)

- **Property names are unique across the whole ontology.** Two entity types may
  only share a property *name* if they also share the same `valueType`. Shared
  keys (`project_id`, `wbs_id`, `equipment_tag`, `supplier_id`, …) are all
  **String** everywhere — safe to reuse. **Do not** reuse a generic name like
  `status`; this design uses entity-specific names (`po_status`, `permit_status`,
  `wo_status`, `bid_award_status`, `ec_status`) to avoid collisions.
- **Key properties** (`entityIdParts`) may only be **String** or **BigInt**.
  All our keys are String IDs.
- **Value-type mapping** (source → ontology): text→`String`, `int/bigint`→
  `BigInt`, `double/decimal/real`→`Double`, `boolean`→`Boolean`,
  `date/datetime/timestamp`→`DateTime`.
- **Entity type name** in the portal: 1–26 chars, alphanumeric/`-`/`_`, must
  start and end alphanumeric.
- Set each entity type's **display-name property** (below) so instances read as
  friendly names in the graph, not raw IDs.

---

## 4. Entity types

For each: **Key** = the property in `entityIdParts`; **Display name** = the
property shown for an instance; **Static binding** = the managed lakehouse table;
map every listed property to its **source column** (same name unless noted).

### 4.1 Project  🟦 *analytics + AI*
- **Key:** `project_id` · **Display:** `project_name`
- **Static binding:** `gold.project_schedule_risk` *(one wide row per project:
  descriptive + the fused Schedule Risk Score — the analytics money table)*

| Property | valueType | Source column |
|---|---|---|
| project_id | String | project_id |
| project_name | String | project_name |
| client | String | client |
| region | String | region |
| contract_type | String | contract_type |
| pct_complete | Double | pct_complete |
| planned_finish | DateTime | planned_finish |
| forecast_finish | DateTime | forecast_finish |
| schedule_slip_days | Double | schedule_slip_days |
| min_total_float_days | Double | min_total_float_days |
| critical_path_at_risk | BigInt | critical_path_at_risk |
| late_long_lead_pos | BigInt | late_long_lead_pos |
| forecast_overrun | Double | forecast_overrun |
| cost_to_complete | Double | cost_to_complete |
| earned_value | Double | earned_value |
| schedule_risk_score | Double | schedule_risk_score |
| risk_band | String | risk_band |

> Need the map (lat/lon) as ontology properties too? Add `latitude`,`longitude`
> to `gold.project_schedule_risk` (join `silver.dim_project`) — only one static
> binding is allowed per entity type, so extend this table rather than adding a
> second binding.

### 4.2 WorkPackage  🟦 *analytics — the SAP ↔ non-SAP bridge*
- **Key:** `wbs_id` · **Display:** `wbs_name`
- **Static binding:** `silver.dim_wbs`

| Property | valueType | Source column |
|---|---|---|
| wbs_id | String | wbs_id |
| project_id | String | project_id |
| wbs_name | String | wbs_name |
| discipline | String | discipline |

### 4.3 Equipment  🟩 *THE real-time + AI star (static + time-series)*
- **Key:** `equipment_tag` · **Display:** `equipment_tag`
- **Static binding:** `silver.dim_equipment`
- **Time-series binding:** Eventhouse `commissioning_telemetry` (see §5)

Static properties:

| Property | valueType | Source column |
|---|---|---|
| equipment_tag | String | equipment_tag |
| asset_id | String | asset_id |
| project_id | String | project_id |
| wbs_id | String | wbs_id |
| asset_class | String | asset_class |
| manufacturer | String | manufacturer |
| model_no | String | model_no |
| criticality | String | criticality |
| install_date | DateTime | install_date |
| operational_status | String | operational_status |

### 4.4 Supplier  🟦🟨 *analytics + AI — the hero-thread hinge*
- **Key:** `supplier_id` · **Display:** `supplier_name`
- **Static binding:** `silver.sap_supplier`

| Property | valueType | Source column |
|---|---|---|
| supplier_id | String | supplier_id |
| supplier_name | String | supplier_name |
| country | String | country |
| risk_rating | String | risk_rating |

### 4.5 PurchaseOrder  🟦 *analytics (SAP procurement signal)*
- **Key:** `po_id` · **Display:** `po_id`
- **Static binding:** `silver.sap_mm_po`

| Property | valueType | Source column |
|---|---|---|
| po_id | String | po_id |
| project_id | String | project_id |
| wbs_id | String | wbs_id |
| supplier_id | String | supplier_id |
| material_desc | String | material_desc |
| is_long_lead | Boolean | is_long_lead |
| po_status | String | status |
| promised_date | DateTime | promised_date |
| revised_date | DateTime | revised_date |

### 4.6 RFQ  🟨 *AI — bid evaluation*
- **Key:** `rfq_id` · **Display:** `equipment_desc`
- **Static binding:** `silver.dim_rfq`

| Property | valueType | Source column |
|---|---|---|
| rfq_id | String | rfq_id |
| equipment_tag | String | equipment_tag |
| material_category | String | material_category |
| equipment_desc | String | equipment_desc |
| engineers_estimate | Double | engineers_estimate |
| required_on_site | DateTime | required_on_site |
| bids_due_date | DateTime | bids_due_date |

### 4.7 Bid  🟨 *AI — TBE/CBE outcome*
- **Key:** `bid_id` · **Display:** `supplier_name`
- **Static binding:** `gold.bid_evaluation` *(carries technical + commercial
  roll-up and the award recommendation)*

| Property | valueType | Source column |
|---|---|---|
| bid_id | String | bid_id |
| rfq_id | String | rfq_id |
| project_id | String | project_id |
| supplier_id | String | supplier_id |
| supplier_name | String | supplier_name |
| supplier_risk | String | supplier_risk |
| quoted_price | Double | quoted_price |
| evaluated_price | Double | evaluated_price |
| price_loading | Double | price_loading |
| delivery_weeks | BigInt | delivery_weeks |
| technical_score | Double | technical_score |
| tbe_status | String | tbe_status |
| is_technically_qualified | Boolean | is_technically_qualified |
| cbe_rank | BigInt | cbe_rank |
| bid_award_status | String | award_status |
| recommended | Boolean | recommended |

### 4.8 WorkOrder  🟩 *real-time context (batch ↔ field)*
- **Key:** `wo_id` · **Display:** `wo_type`
- **Static binding:** `silver.fact_work_order`

| Property | valueType | Source column |
|---|---|---|
| wo_id | String | wo_id |
| equipment_tag | String | equipment_tag |
| project_id | String | project_id |
| wbs_id | String | wbs_id |
| wo_type | String | wo_type |
| priority | String | priority |
| wo_status | String | wo_status |
| reported_date | DateTime | reported_date |
| completed_date | DateTime | completed_date |

### 4.9 Permit  🟦 *cross-cutting (S3 government data)*
- **Key:** `permit_id` · **Display:** `permit_type`
- **Static binding:** `silver.dim_permit`

| Property | valueType | Source column |
|---|---|---|
| permit_id | String | permit_id |
| project_id | String | project_id |
| authority_id | String | authority_id |
| permit_type | String | permit_type |
| permit_status | String | permit_status |
| issued_date | DateTime | issued_date |
| expiry_date | DateTime | expiry_date |
| valuation_usd | Double | valuation_usd |

### 4.10 EngineeringChange  🟦 *analytics (non-SAP schedule signal)*
- **Key:** `ec_id` · **Display:** `title`
- **Static binding:** `silver.fact_engineering_change`

| Property | valueType | Source column |
|---|---|---|
| ec_id | String | ec_id |
| project_id | String | project_id |
| wbs_id | String | wbs_id |
| title | String | title |
| discipline | String | discipline |
| ec_status | String | status |
| schedule_impact_days | BigInt | schedule_impact_days |
| issued_date | DateTime | issued_date |

---

## 5. Equipment time-series binding (the RTI showcase)

Add this **after** the Equipment static binding exists (§4.3). Bind a *second*
data source of type **TimeSeries** to the **same** Equipment entity type.

- **Source:** Eventhouse (KustoTable)
  - `clusterUri`: `https://trd-psr494w5ftntwyskww.z3.kusto.fabric.microsoft.com`
  - `databaseName`: `eh_rti_telemetry`
  - `sourceTableName`: `commissioning_telemetry`
- **Timestamp column:** `event_time` → bind to a `DateTime` time-series property.
- **Join key:** the telemetry's `equipment_tag` column links each reading to the
  Equipment instance (same key as the static binding).

Add these **time-series properties** to the Equipment entity type and map them:

| TS property | valueType | Source column |
|---|---|---|
| event_time | DateTime | event_time |
| commissioning_phase | String | commissioning_phase |
| winding_temp_c | Double | winding_temp_c |
| top_oil_temp_c | Double | top_oil_temp_c |
| load_current_a | Double | load_current_a |
| load_pct | Double | load_pct |
| dga_h2_ppm | Double | dga_h2_ppm |
| vibration_mm_s | Double | vibration_mm_s |
| tap_position | BigInt | tap_position |
| cooling_stage | String | cooling_stage |
| telemetry_status | String | status |

> Result: **ET-1001** is one entity with its nameplate/criticality (static, from
> BigQuery) **and** its live winding-temp / dissolved-gas trend (time-series,
> from the Eventhouse) — the exact fusion the demo narrates. `telemetry_status`
> (`alarm`) is what the Activator/operations-agent story reacts to.

---

## 6. Relationship types

A relationship needs a **link table** (managed lakehouse table) that physically
contains **both** entity keys. Configure each below by pointing the relationship
at the link table and mapping **source key column** and **target key column**.
(In the portal: create the relationship type, then add a *contextualization*
that binds the two key columns.)

| # | Relationship (source → target) | Link table | Source key col | Target key col |
|---|---|---|---|---|
| 1 | Project **contains** WorkPackage | `silver.dim_wbs` | project_id | wbs_id |
| 2 | Project **hasAsset** Equipment | `silver.dim_equipment` | project_id | equipment_tag |
| 3 | WorkPackage **scopes** Equipment | `silver.dim_equipment` | wbs_id | equipment_tag |
| 4 | WorkPackage **procuredVia** PurchaseOrder | `silver.sap_mm_po` | wbs_id | po_id |
| 5 | Supplier **fulfills** PurchaseOrder | `silver.sap_mm_po` | supplier_id | po_id |
| 6 | Project **issues** RFQ | `silver.dim_rfq`* | project_id | rfq_id |
| 7 | RFQ **forEquipment** Equipment | `silver.dim_rfq` | rfq_id | equipment_tag |
| 8 | RFQ **receivesBid** Bid | `gold.bid_evaluation` | rfq_id | bid_id |
| 9 | Supplier **submits** Bid | `gold.bid_evaluation` | supplier_id | bid_id |
| 10 | Equipment **hasWorkOrder** WorkOrder | `silver.fact_work_order` | equipment_tag | wo_id |
| 11 | WorkPackage **affectedByChange** EngineeringChange | `silver.fact_engineering_change` | wbs_id | ec_id |
| 12 | Project **hasPermit** Permit | `silver.dim_permit` | project_id | permit_id |

> \* Relationship #6 needs `project_id` in the RFQ link table. `silver.dim_rfq`
> may not carry `project_id` directly — if not, use `gold.bid_evaluation`
> (has both `project_id` and `rfq_id`) as the link table instead, or add
> `project_id` to `dim_rfq`. Verify the column exists before binding.

**Contextualization rule:** each mapped key column must correspond to a property
that is part of that entity type's key (`entityIdParts`). All keys above are the
single-column String keys from §4, so each contextualization maps exactly one
source column and one target column.

---

## 7. Manual configuration order (do it in this sequence)

1. **Prep sources** — run the §2 CTAS to create `silver.dim_equipment`,
   `silver.fact_work_order`, `silver.dim_permit`; confirm all 10 source tables
   are **managed** and column-mapping-free. Collect the workspace/lakehouse/
   eventhouse IDs.
2. **Create the Ontology item** in the lakehouse workspace (name e.g.
   `ProjectControlsIQ-Ontology`).
3. **Create the 10 entity types** (§4). For each: set name, add properties with
   the right `valueType`, mark the key property, set the display-name property.
   *Don't add bindings yet if the UI lets you batch — but bindings can also be
   added per entity as you go.*
4. **Add static bindings** — one managed lakehouse table per entity type; map
   every property to its source column.
5. **Add the Equipment time-series binding** (§5) — only after Equipment's static
   binding exists.
6. **Create the 12 relationship types** (§6), each with its contextualization
   link table + key-column mapping. Verify each link table actually contains
   both key columns first (esp. #6).
7. **Refresh** the ontology (bindings are **manual refresh** — data changes
   upstream do not auto-propagate).
8. **Validate** with the §8 graph walks.
9. *(Optional)* Add **Overviews** widgets to Equipment (line chart of
   `winding_temp_c` / `dga_h2_ppm`) and **ResourceLinks** to the EPCDemo Power BI
   reports (§9).

---

## 8. Validation — prove each pillar with a graph walk

After refresh, run these to confirm the ontology tells the story:

- **Analytics:** from `Project` **Falcon (PRJ-001)** → `contains` WorkPackage →
  `procuredVia` PurchaseOrder; confirm the **late long-lead PO (PO-00512)** and
  the project's `schedule_risk_score` (~96) resolve. Then Project →
  `affectedByChange` EngineeringChange surfaces **EC-1207**.
- **Real-time:** from `Equipment` **ET-1001** read the time-series
  `winding_temp_c` / `telemetry_status`; confirm the latest reading is `alarm`
  and `hasWorkOrder` surfaces **WO-900001**.
- **AI / bid eval:** from `RFQ-0001` → `receivesBid` Bid; confirm the **cheapest**
  bid is `is_technically_qualified = false` and its `Supplier` (via `submits`) is
  the **same high-risk supplier** that `fulfills` PO-00512. **This single
  traversal is the whole hero thread** — if it resolves, the ontology is done.
- **Cross-cutting:** Project **Falcon** → `hasPermit` Permit returns the
  jurisdiction permits/inspections context.

---

## 9. Optional polish (portal parts)

- **Overviews** on `Equipment`: `lineChart` widget, source `winding_temp_c` (and
  a second for `dga_h2_ppm`), aggregation `Average`, interval `FifteenMinutes`,
  fixed range `Last4Hours` — mirrors the RTI dashboard inside the ontology view.
- **ResourceLinks** on `Project` and `Bid`: `type: PowerBIReport` pointing at the
  **Portfolio Schedule Risk** and **Bid Evaluation** reports so users jump from a
  graph node to the matching dashboard.
- **Documents** on `Supplier`: link the supplier quotation MD files in
  `docs/bids/` for quick reference during the bid-eval demo.

---

## 10. Appendix — entity/relationship cross-reference

| Entity type | Key | Static source (managed) | Time-series source | Pillars |
|---|---|---|---|---|
| Project | project_id | gold.project_schedule_risk | — | analytics, AI |
| WorkPackage | wbs_id | silver.dim_wbs | — | analytics |
| Equipment | equipment_tag | silver.dim_equipment | eh `commissioning_telemetry` | real-time, AI |
| Supplier | supplier_id | silver.sap_supplier | — | analytics, AI |
| PurchaseOrder | po_id | silver.sap_mm_po | — | analytics |
| RFQ | rfq_id | silver.dim_rfq | — | AI |
| Bid | bid_id | gold.bid_evaluation | — | AI |
| WorkOrder | wo_id | silver.fact_work_order | — | real-time |
| Permit | permit_id | silver.dim_permit | — | cross-cutting |
| EngineeringChange | ec_id | silver.fact_engineering_change | — | analytics |

12 relationship types wire these into one graph (§6). The design deliberately
routes every hero-thread hop — Supplier↔PO, Supplier↔Bid, RFQ↔Equipment,
Equipment↔telemetry — through a real key that already exists in a managed table,
so nothing here requires new source data beyond the three §2 CTAS copies.
