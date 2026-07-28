"""Author the Fabric medallion notebooks as .ipynb files.

Notebooks are maintained here as code (readable diffs) and emitted as Fabric-compatible
.ipynb (nbformat 4.5, Synapse PySpark kernel). scripts/10_provision_fabric.ps1 imports the
emitted files into the workspace; scripts/20_load_data.ps1 runs them in order.

Run:  python fabric/notebooks/build_notebooks.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Tables landed as Parquet in Files/landing (see data_gen/generate.py output).
TABLES = [
    "dim_project", "dim_wbs", "fact_schedule_activity", "sap_fi_cost",
    "sap_mm_po", "sap_supplier", "fact_engineering_change", "ext_disruption_signal",
    "dim_rfq", "dim_tech_requirement", "fact_bid", "fact_bid_tech_eval",
]


def _lines(code: str) -> list[str]:
    """Split a code/markdown block into nbformat 'source' lines (each keeps its newline)."""
    text = code.strip("\n") + "\n"
    parts = text.splitlines(keepends=True)
    return parts


def md(code: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(code)}


def code(src: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": _lines(src)}


def notebook(cells: list[dict]) -> dict:
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "language_info": {"name": "python"},
            "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
        },
        "cells": cells,
    }


# --------------------------------------------------------------------------- 01
def nb_01_setup() -> dict:
    return notebook([
        md("""
# 01 - Setup Lakehouse
Creates the medallion schemas (`bronze`, `silver`, `gold`) in the schema-enabled
Project-Intelligence Lakehouse. Attach the Lakehouse as the default lakehouse before running.
"""),
        code("""
for schema in ['bronze', 'silver', 'gold']:
    spark.sql(f'CREATE SCHEMA IF NOT EXISTS {schema}')
    print(f'schema ready: {schema}')
"""),
    ])


# --------------------------------------------------------------------------- 02
def nb_02_bronze() -> dict:
    tbls = ", ".join(f"'{t}'" for t in TABLES)
    return notebook([
        md("""
# 02 - Load Bronze
Reads each raw Parquet file from `Files/landing/` and writes it as a Delta table in the
**`bronze`** schema (`bronze.<table>`).

> **Coexistence narrative:** in production the **SAP** tables (`sap_fi_cost`, `sap_mm_po`,
> `sap_supplier`) arrive via **SAP BDC Connect / mirroring** (zero-copy from S/4HANA on Azure
> via RISE), while the **non-SAP** tables (schedule, engineering change, project/WBS master)
> arrive via **OneLake shortcuts** (data stays in Primavera / PC&E, connected in place). For
> the synthetic demo they are all local Delta, but the origin_system column keeps the story literal.
"""),
        code(f"""
LANDING = 'Files/landing'
tables = [{tbls}]

spark.sql('CREATE SCHEMA IF NOT EXISTS bronze')
for t in tables:
    df = spark.read.parquet(f'{{LANDING}}/{{t}}.parquet')
    (df.write.format('delta').mode('overwrite')
        .option('overwriteSchema', 'true').saveAsTable(f'bronze.{{t}}'))
    print(f'bronze.{{t:26s}} {{df.count():>8,}} rows')
print('Bronze load complete.')
"""),
    ])


# --------------------------------------------------------------------------- 03
def nb_03_silver_gold() -> dict:
    return notebook([
        md("""
# 03 - Build Silver + Gold
**Silver:** light typing (dates/booleans) and pass-through of the twelve bronze tables.
**Gold:** the cross-system model. `gold.project_schedule_risk` fuses **non-SAP** schedule
signals with **SAP** cost + procurement signals into one governed, per-project risk table —
the single load-bearing join no source system does alone. `gold.bid_evaluation` +
`gold.rfq_award_recommendation` support the **Technical / Commercial Bid Evaluation** use cases,
fusing the non-SAP technical compliance with the SAP commercial evaluation into an award
recommendation. Curated driver tables support drill-down.
"""),
        code("""
from pyspark.sql import functions as F

# ---- SILVER: typed pass-through ----
spark.sql('CREATE SCHEMA IF NOT EXISTS silver')

date_cols = {
    'dim_project': ['start_date', 'planned_finish', 'forecast_finish'],
    'fact_schedule_activity': ['baseline_start', 'baseline_finish', 'forecast_finish', 'actual_finish'],
    'sap_fi_cost': ['period'],
    'sap_mm_po': ['promised_date', 'revised_date'],
    'fact_engineering_change': ['issued_date'],
    'ext_disruption_signal': ['event_date'],
    'dim_rfq': ['issued_date', 'bids_due_date', 'required_on_site'],
    'fact_bid': ['bid_date'],
}
tables = ['dim_project', 'dim_wbs', 'fact_schedule_activity', 'sap_fi_cost',
          'sap_mm_po', 'sap_supplier', 'fact_engineering_change', 'ext_disruption_signal',
          'dim_rfq', 'dim_tech_requirement', 'fact_bid', 'fact_bid_tech_eval']
for t in tables:
    df = spark.table(f'bronze.{t}')
    for c in date_cols.get(t, []):
        if c in df.columns:
            df = df.withColumn(c, F.to_date(F.col(c)))
    df.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').saveAsTable(f'silver.{t}')
    print(f'silver.{t} ok')
"""),
        code("""
# ---- GOLD: create the schema (driver aggregations are inlined as CTEs below) ----
spark.sql('CREATE SCHEMA IF NOT EXISTS gold')
print('gold schema ready')
"""),
        code("""
# ---- GOLD: the fused per-project schedule-risk table (single statement) ----
# All driver aggregations are inlined as CTEs that read silver.* DIRECTLY. Temp views were
# tried first but a CTAS on a schema-enabled Lakehouse re-resolves a temp view's body in a
# different catalog context and fails with TABLE_OR_VIEW_NOT_FOUND on silver.*; direct
# silver.* references inside the CTAS resolve fine. Also avoids reading the gold table while
# overwriting it (self-referential CREATE OR REPLACE fails on Delta).
spark.sql('''
CREATE OR REPLACE TABLE gold.project_schedule_risk
USING delta AS
WITH v_sched AS (            -- non-SAP schedule signals (Primavera)
    SELECT project_id,
           MAX(GREATEST(DATEDIFF(forecast_finish, baseline_finish), 0)) AS max_slip_days,
           MIN(total_float_days) AS min_float,
           SUM(CASE WHEN is_critical_path AND forecast_finish > baseline_finish THEN 1 ELSE 0 END) AS cp_at_risk
    FROM silver.fact_schedule_activity GROUP BY project_id
),
v_po AS (                   -- SAP procurement signal (late long-lead POs)
    SELECT project_id,
           SUM(CASE WHEN is_long_lead AND status = 'Late' THEN 1 ELSE 0 END) AS late_long_lead_pos
    FROM silver.sap_mm_po GROUP BY project_id
),
v_cost AS (                 -- SAP finance signal (overrun + cost-to-complete + EV)
    SELECT project_id,
           SUM(forecast_cost - budget) AS forecast_overrun,
           SUM(cost_to_complete)       AS cost_to_complete,
           SUM(earned_value)           AS earned_value
    FROM silver.sap_fi_cost GROUP BY project_id
),
scored AS (
    SELECT
        p.project_id, p.project_name, p.client, p.region, p.contract_type,
        p.pct_complete, p.planned_finish, p.forecast_finish,
        COALESCE(s.max_slip_days, 0)       AS schedule_slip_days,      -- non-SAP
        COALESCE(s.min_float, 0)           AS min_total_float_days,    -- non-SAP
        COALESCE(s.cp_at_risk, 0)          AS critical_path_at_risk,   -- non-SAP
        COALESCE(po.late_long_lead_pos, 0) AS late_long_lead_pos,      -- SAP
        COALESCE(c.forecast_overrun, 0)    AS forecast_overrun,        -- SAP
        COALESCE(c.cost_to_complete, 0)    AS cost_to_complete,        -- SAP
        COALESCE(c.earned_value, 0)        AS earned_value,            -- SAP
        LEAST(100,
            COALESCE(s.max_slip_days, 0) * 1.5
          + CASE WHEN COALESCE(s.min_float, 0) < 0 THEN -s.min_float ELSE 0 END * 2
          + COALESCE(s.cp_at_risk, 0) * 3
          + COALESCE(po.late_long_lead_pos, 0) * 5
          + COALESCE(c.forecast_overrun, 0) / 100000
        ) AS schedule_risk_score
    FROM silver.dim_project p
    LEFT JOIN v_sched s ON p.project_id = s.project_id
    LEFT JOIN v_po   po ON p.project_id = po.project_id
    LEFT JOIN v_cost c  ON p.project_id = c.project_id
)
SELECT *,
    CASE WHEN schedule_risk_score >= 61 THEN 'Red'
         WHEN schedule_risk_score >= 26 THEN 'Amber'
         ELSE 'Green' END AS risk_band
FROM scored
''')

spark.sql('''
ALTER TABLE gold.project_schedule_risk SET TBLPROPERTIES ('note' = 'fuses SAP + non-SAP signals')
''')

print('gold.project_schedule_risk built. Top 5 by risk:')
spark.sql('''
SELECT project_id, project_name, ROUND(schedule_risk_score,1) AS score, risk_band,
       schedule_slip_days, min_total_float_days, critical_path_at_risk,
       late_long_lead_pos, ROUND(forecast_overrun,0) AS overrun
FROM gold.project_schedule_risk ORDER BY schedule_risk_score DESC LIMIT 5
''').show(truncate=False)
"""),
        code("""
# ---- GOLD: curated driver-detail tables for dashboard + agent drill-down ----
# Falcon's cross-system 'why' on one row set: at-risk critical-path activities + their EC (non-SAP),
# the late long-lead PO + supplier (SAP), and the cost exposure (SAP).
spark.sql('''
CREATE OR REPLACE TABLE gold.at_risk_activities USING delta AS
SELECT a.project_id, a.wbs_id, a.activity_id, a.activity_name, a.discipline_hint,
       a.baseline_finish, a.forecast_finish, a.total_float_days, a.is_critical_path,
       e.ec_id, e.title AS ec_title, e.status AS ec_status, e.schedule_impact_days
FROM (SELECT fsa.*, w.discipline AS discipline_hint
      FROM silver.fact_schedule_activity fsa
      JOIN silver.dim_wbs w ON fsa.wbs_id = w.wbs_id) a
LEFT JOIN silver.fact_engineering_change e ON e.affected_activity_id = a.activity_id
WHERE a.is_critical_path AND a.forecast_finish > a.baseline_finish
''')

spark.sql('''
CREATE OR REPLACE TABLE gold.late_procurement USING delta AS
SELECT po.project_id, po.wbs_id, po.po_id, po.material_desc, po.is_long_lead,
       po.promised_date, po.revised_date, DATEDIFF(po.revised_date, po.promised_date) AS days_late,
       s.supplier_id, s.supplier_name, s.country, s.risk_rating
FROM silver.sap_mm_po po
JOIN silver.sap_supplier s ON po.supplier_id = s.supplier_id
WHERE po.status = 'Late'
''')
print('gold.at_risk_activities and gold.late_procurement built.')
"""),
        code("""
# ---- GOLD: bid-evaluation tables for the TBE/CBE use cases (dashboard + agent) ----
# gold.bid_evaluation: one row per supplier bid, joined to its RFQ / project / supplier, carrying
# the technical (TBE) roll-up and the commercial (CBE) evaluated price + award recommendation.
spark.sql('''
CREATE OR REPLACE TABLE gold.bid_evaluation USING delta AS
SELECT
    b.bid_id, b.rfq_id, b.project_id, p.project_name, p.client,
    r.equipment_tag, r.material_category, r.equipment_desc,
    r.engineers_estimate, r.required_on_site, r.bids_due_date,
    b.supplier_id, b.supplier_name, s.country AS supplier_country, s.risk_rating AS supplier_risk,
    b.quoted_price, b.spares_price, b.freight_price,
    (b.quoted_price + b.spares_price + b.freight_price) AS total_quoted,
    b.delivery_weeks, b.weeks_late, b.payment_advance_pct, b.warranty_months, b.incoterms,
    b.technical_score, b.tech_compliant_count, b.tech_deviation_count, b.tech_exception_count,
    b.tbe_status, b.is_technically_qualified,
    b.commercial_deviation_count, b.price_loading, b.evaluated_price, b.cbe_rank,
    b.award_status, b.recommended
FROM silver.fact_bid b
JOIN silver.dim_rfq r      ON b.rfq_id = r.rfq_id
JOIN silver.dim_project p  ON b.project_id = p.project_id
JOIN silver.sap_supplier s ON b.supplier_id = s.supplier_id
''')

# gold.rfq_award_recommendation: one row per RFQ contrasting the lowest quoted bid with the
# recommended (lowest evaluated, technically qualified) award — the load-bearing CBE insight.
spark.sql('''
CREATE OR REPLACE TABLE gold.rfq_award_recommendation USING delta AS
WITH lowest_quote AS (
    SELECT rfq_id, supplier_name AS lowest_quote_supplier, quoted_price AS lowest_quoted_price,
           is_technically_qualified AS lowest_quote_qualified,
           ROW_NUMBER() OVER (PARTITION BY rfq_id ORDER BY quoted_price ASC) AS rn
    FROM silver.fact_bid
),
recommended AS (
    SELECT rfq_id, supplier_name AS recommended_supplier, quoted_price AS recommended_quoted,
           evaluated_price AS recommended_evaluated, technical_score AS recommended_tech_score
    FROM silver.fact_bid WHERE recommended = true
)
SELECT r.rfq_id, r.project_id, r.equipment_tag, r.material_category, r.bidder_count,
       lq.lowest_quote_supplier, lq.lowest_quoted_price, lq.lowest_quote_qualified,
       rc.recommended_supplier, rc.recommended_quoted, rc.recommended_evaluated, rc.recommended_tech_score,
       (rc.recommended_evaluated - lq.lowest_quoted_price) AS evaluated_vs_lowest_quote
FROM silver.dim_rfq r
LEFT JOIN (SELECT * FROM lowest_quote WHERE rn = 1) lq ON r.rfq_id = lq.rfq_id
LEFT JOIN recommended rc ON r.rfq_id = rc.rfq_id
''')

print('gold.bid_evaluation and gold.rfq_award_recommendation built. Hero RFQ-0001:')
spark.sql('''
SELECT supplier_name, ROUND(quoted_price,0) AS quoted, ROUND(evaluated_price,0) AS evaluated,
       technical_score, tbe_status, award_status
FROM gold.bid_evaluation WHERE rfq_id = 'RFQ-0001' ORDER BY evaluated_price
''').show(truncate=False)
print('Gold layer complete.')
"""),
    ])


def main() -> int:
    outputs = {
        "01_setup_lakehouse.ipynb": nb_01_setup(),
        "02_load_bronze.ipynb": nb_02_bronze(),
        "03_build_silver_gold.ipynb": nb_03_silver_gold(),
    }
    for fname, nb in outputs.items():
        (HERE / fname).write_text(json.dumps(nb, indent=1), encoding="utf-8")
        print(f"wrote {fname}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
