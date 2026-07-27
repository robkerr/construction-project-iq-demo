#!/usr/bin/env python
"""Generate the TMDL definition for the **ProjectControlsIQ** Direct Lake semantic model.

Emits a PBIP-style `ProjectControlsIQ.SemanticModel/` folder (definition.pbism + definition/*)
that maps 1:1 to the Lakehouse `silver` tables. Direct Lake partitions read live from OneLake via
a single shared `AzureStorage.DataLake` named expression. Measures are ported verbatim from
`fabric/measures.dax` so the model's ranking matches `data_gen/generate.py`.

Workspace + Lakehouse IDs are read from the repo `.env` (FABRIC_WORKSPACE_ID / FABRIC_LAKEHOUSE_ID),
or can be passed with --workspace / --lakehouse. Deploy the emitted folder with
`scripts/30_deploy_semantic_model.ps1`.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path

MODEL_NAME = "ProjectControlsIQ"
DL_EXPR = "DL_ProjectControlsIQ"          # shared Direct Lake named expression
SCHEMA = "silver"
TAB = "\t"

# --------------------------------------------------------------------------- schema
# (name, dataType, sourceColumn, hidden, summarizeBy)  -- summarizeBy None => omit
COLS = {
    "dim_project": [
        ("project_id", "string", "project_id", False, None),
        ("project_name", "string", "project_name", False, None),
        ("client", "string", "client", False, None),
        ("region", "string", "region", False, None),
        ("contract_type", "string", "contract_type", False, None),
        ("start_date", "dateTime", "start_date", False, None),
        ("planned_finish", "dateTime", "planned_finish", False, None),
        ("forecast_finish", "dateTime", "forecast_finish", False, None),
        ("pct_complete", "double", "pct_complete", False, "none"),
        ("is_active", "boolean", "is_active", False, None),
        ("origin_system", "string", "origin_system", False, None),
    ],
    "dim_wbs": [
        ("wbs_id", "string", "wbs_id", False, None),
        ("project_id", "string", "project_id", True, None),
        ("wbs_name", "string", "wbs_name", False, None),
        ("discipline", "string", "discipline", False, None),
        ("origin_system", "string", "origin_system", False, None),
    ],
    "fact_schedule_activity": [
        ("activity_id", "string", "activity_id", False, None),
        ("wbs_id", "string", "wbs_id", True, None),
        ("project_id", "string", "project_id", True, None),
        ("activity_name", "string", "activity_name", False, None),
        ("baseline_start", "dateTime", "baseline_start", False, None),
        ("baseline_finish", "dateTime", "baseline_finish", False, None),
        ("forecast_finish", "dateTime", "forecast_finish", False, None),
        ("actual_finish", "dateTime", "actual_finish", False, None),
        ("total_float_days", "int64", "total_float_days", False, "none"),
        ("is_critical_path", "boolean", "is_critical_path", False, None),
        ("origin_system", "string", "origin_system", False, None),
    ],
    "fact_engineering_change": [
        ("ec_id", "string", "ec_id", False, None),
        ("project_id", "string", "project_id", True, None),
        ("wbs_id", "string", "wbs_id", True, None),
        ("title", "string", "title", False, None),
        ("discipline", "string", "discipline", False, None),
        ("issued_date", "dateTime", "issued_date", False, None),
        ("status", "string", "status", False, None),
        ("schedule_impact_days", "int64", "schedule_impact_days", False, "none"),
        ("affected_activity_id", "string", "affected_activity_id", False, None),
        ("origin_system", "string", "origin_system", False, None),
    ],
    "sap_fi_cost": [
        ("project_id", "string", "project_id", True, None),
        ("wbs_id", "string", "wbs_id", True, None),
        ("period", "dateTime", "period", False, None),
        ("budget", "double", "budget", False, "none"),
        ("actual_cost", "double", "actual_cost", False, "none"),
        ("forecast_cost", "double", "forecast_cost", False, "none"),
        ("cost_to_complete", "double", "cost_to_complete", False, "none"),
        ("earned_value", "double", "earned_value", False, "none"),
        ("origin_system", "string", "origin_system", False, None),
    ],
    "sap_mm_po": [
        ("po_id", "string", "po_id", False, None),
        ("project_id", "string", "project_id", True, None),
        ("wbs_id", "string", "wbs_id", True, None),
        ("material_desc", "string", "material_desc", False, None),
        ("supplier_id", "string", "supplier_id", True, None),
        ("promised_date", "dateTime", "promised_date", False, None),
        ("revised_date", "dateTime", "revised_date", False, None),
        ("status", "string", "status", False, None),
        ("is_long_lead", "boolean", "is_long_lead", False, None),
        ("origin_system", "string", "origin_system", False, None),
    ],
    "sap_supplier": [
        ("supplier_id", "string", "supplier_id", False, None),
        ("supplier_name", "string", "supplier_name", False, None),
        ("country", "string", "country", False, None),
        ("risk_rating", "string", "risk_rating", False, None),
        ("origin_system", "string", "origin_system", False, None),
    ],
}

# --------------------------------------------------------------------------- measures
# table -> list of dicts: {name, desc, fmt, dax(single str) OR lines(list)}
MEASURES = {
    "fact_schedule_activity": [
        {"name": "Schedule Slip (days)", "fmt": "#,##0",
         "desc": "Non-SAP: days the project is forecast to finish past its baseline (Primavera).",
         "lines": [
             "VAR _slip =",
             "    MAXX(",
             "        fact_schedule_activity,",
             "        DATEDIFF(fact_schedule_activity[baseline_finish], fact_schedule_activity[forecast_finish], DAY)",
             "    )",
             "RETURN IF(_slip > 0, _slip, 0)",
         ]},
        {"name": "Critical Path At Risk", "fmt": "#,##0",
         "desc": "Non-SAP: count of critical-path activities forecast to finish late.",
         "dax": "CALCULATE(COUNTROWS(fact_schedule_activity), fact_schedule_activity[is_critical_path] = TRUE(), FILTER(fact_schedule_activity, fact_schedule_activity[forecast_finish] > fact_schedule_activity[baseline_finish]))"},
        {"name": "Min Total Float (days)", "fmt": "#,##0",
         "desc": "Non-SAP: minimum total float across activities (negative = behind).",
         "dax": "MIN(fact_schedule_activity[total_float_days])"},
        {"name": "Worst Min Float (days)", "fmt": "#,##0",
         "desc": "Portfolio helper: worst (minimum) total float across activities.",
         "dax": "MIN(fact_schedule_activity[total_float_days])"},
    ],
    "fact_engineering_change": [
        {"name": "Approved EC Schedule Impact (days)", "fmt": "#,##0",
         "desc": "Non-SAP: total schedule impact of approved engineering changes.",
         "dax": 'CALCULATE(SUM(fact_engineering_change[schedule_impact_days]), fact_engineering_change[status] = "Approved")'},
    ],
    "sap_fi_cost": [
        {"name": "Cost To Complete", "fmt": "$#,##0",
         "desc": "SAP FI: remaining cost to complete.",
         "dax": "SUM(sap_fi_cost[cost_to_complete])"},
        {"name": "Forecast Overrun", "fmt": "$#,##0",
         "desc": "SAP FI: forecast cost minus budget (the cost-risk driver).",
         "dax": "SUM(sap_fi_cost[forecast_cost]) - SUM(sap_fi_cost[budget])"},
        {"name": "Earned Value", "fmt": "$#,##0",
         "desc": "SAP FI: earned value to date.",
         "dax": "SUM(sap_fi_cost[earned_value])"},
    ],
    "sap_mm_po": [
        {"name": "Late Long-Lead POs", "fmt": "#,##0",
         "desc": "SAP MM: count of late long-lead purchase orders (the procurement-risk driver).",
         "dax": 'CALCULATE(COUNTROWS(sap_mm_po), sap_mm_po[is_long_lead] = TRUE(), sap_mm_po[status] = "Late")'},
    ],
    "dim_project": [
        {"name": "Schedule Risk Score", "fmt": "#,##0.0",
         "desc": "Fused 0-100 index: combines non-SAP schedule slip/float/critical-path with SAP overrun and late long-lead POs. The single load-bearing metric of the demo.",
         "lines": [
             "VAR _slip = [Schedule Slip (days)]",
             "VAR _float = [Min Total Float (days)]",
             "VAR _cparisk = [Critical Path At Risk]",
             "VAR _overrun = [Forecast Overrun]",
             "VAR _latepo = [Late Long-Lead POs]",
             "RETURN",
             "    MIN(",
             "        100,",
             "        (_slip * 1.5)",
             "            + (IF(_float < 0, -_float, 0) * 2)",
             "            + (_cparisk * 3)",
             "            + (_latepo * 5)",
             "            + DIVIDE(_overrun, 100000)",
             "    )",
         ]},
        {"name": "Risk Band", "fmt": None,
         "desc": "Red/Amber/Green classification of Schedule Risk Score.",
         "lines": [
             "VAR _s = [Schedule Risk Score]",
             "RETURN",
             "    SWITCH(",
             "        TRUE(),",
             '        _s >= 61, "Red",',
             '        _s >= 26, "Amber",',
             '        "Green"',
             "    )",
         ]},
        {"name": "Projects At Risk", "fmt": "#,##0",
         "desc": "Count of projects with Schedule Risk Score >= 26 (Amber or Red).",
         "dax": "CALCULATE(DISTINCTCOUNT(dim_project[project_id]), FILTER(VALUES(dim_project[project_id]), [Schedule Risk Score] >= 26))"},
        {"name": "Total Forecast Overrun", "fmt": "$#,##0",
         "desc": "Portfolio KPI: total forecast overrun (SAP FI).",
         "dax": "[Forecast Overrun]"},
        {"name": "Total Late Long-Lead POs", "fmt": "#,##0",
         "desc": "Portfolio KPI: total late long-lead POs (SAP MM).",
         "dax": "[Late Long-Lead POs]"},
    ],
}

# --------------------------------------------------------------------------- relationships
# (name, fromTable, fromCol, toTable, toCol)  -- from = many (fact), to = one (dim)
RELATIONSHIPS = [
    ("rel_project_wbs", "dim_wbs", "project_id", "dim_project", "project_id"),
    ("rel_wbs_schedule", "fact_schedule_activity", "wbs_id", "dim_wbs", "wbs_id"),
    ("rel_wbs_ec", "fact_engineering_change", "wbs_id", "dim_wbs", "wbs_id"),
    ("rel_wbs_ficost", "sap_fi_cost", "wbs_id", "dim_wbs", "wbs_id"),
    ("rel_wbs_po", "sap_mm_po", "wbs_id", "dim_wbs", "wbs_id"),
    ("rel_supplier_po", "sap_mm_po", "supplier_id", "sap_supplier", "supplier_id"),
]


def q(name: str) -> str:
    """Quote a TMDL identifier if it contains spaces or special chars."""
    if any(c in name for c in " .'=:()-"):
        return "'" + name.replace("'", "''") + "'"
    return name


def measure_tmdl(m: dict) -> list[str]:
    out = []
    for d in m["desc"].split("\n"):
        out.append(f"{TAB}/// {d}")
    if "lines" in m:
        out.append(f"{TAB}measure {q(m['name'])} = ```")
        for ln in m["lines"]:
            out.append(f"{TAB}{TAB}{TAB}{ln}")
        out.append(f"{TAB}{TAB}{TAB}```")
    else:
        out.append(f"{TAB}measure {q(m['name'])} = {m['dax']}")
    if m.get("fmt"):
        out.append(f"{TAB}{TAB}formatString: {m['fmt']}")
    out.append("")
    return out


def table_tmdl(tname: str) -> str:
    out = [f"table {q(tname)}", ""]
    for m in MEASURES.get(tname, []):
        out += measure_tmdl(m)
    for (cname, dtype, scol, hidden, sby) in COLS[tname]:
        out.append(f"{TAB}column {q(cname)}")
        out.append(f"{TAB}{TAB}dataType: {dtype}")
        if hidden:
            out.append(f"{TAB}{TAB}isHidden")
        if sby:
            out.append(f"{TAB}{TAB}summarizeBy: {sby}")
        out.append(f"{TAB}{TAB}sourceColumn: {scol}")
        out.append("")
    out.append(f"{TAB}partition {q(tname)} = entity")
    out.append(f"{TAB}{TAB}mode: directLake")
    out.append(f"{TAB}{TAB}source")
    out.append(f"{TAB}{TAB}{TAB}entityName: {tname}")
    out.append(f"{TAB}{TAB}{TAB}schemaName: {SCHEMA}")
    out.append(f"{TAB}{TAB}{TAB}expressionSource: {DL_EXPR}")
    out.append("")
    return "\n".join(out)


def relationships_tmdl() -> str:
    out = []
    for (rname, ft, fc, tt, tc) in RELATIONSHIPS:
        out.append(f"relationship {rname}")
        out.append(f"{TAB}fromColumn: {q(ft)}.{q(fc)}")
        out.append(f"{TAB}toColumn: {q(tt)}.{q(tc)}")
        out.append("")
    return "\n".join(out)


def model_tmdl() -> str:
    out = [
        "model Model",
        f"{TAB}culture: en-US",
        f"{TAB}defaultPowerBIDataSourceVersion: powerBI_V3",
        f"{TAB}sourceQueryCulture: en-US",
        f"{TAB}dataAccessOptions",
        f"{TAB}{TAB}legacyRedirects",
        f"{TAB}{TAB}returnErrorValuesAsNull",
        "",
    ]
    for tname in COLS:
        out.append(f"ref table {q(tname)}")
    out.append("")
    return "\n".join(out)


def expressions_tmdl(ws: str, lh: str) -> str:
    url = f"https://onelake.dfs.fabric.microsoft.com/{ws}/{lh}"
    return "\n".join([
        f"/// Shared Direct Lake source pointing at the {MODEL_NAME} Lakehouse in OneLake.",
        f"expression {DL_EXPR} =",
        f"{TAB}{TAB}let",
        f'{TAB}{TAB}{TAB}Source = AzureStorage.DataLake("{url}", [HierarchicalNavigation=true])',
        f"{TAB}{TAB}in",
        f"{TAB}{TAB}{TAB}Source",
        "",
    ])


PBISM = """{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {
    "qnaEnabled": true
  }
}
"""

DATABASE = "database\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n"

PLATFORM = """{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {
    "type": "SemanticModel",
    "displayName": "%s"
  },
  "config": {
    "version": "2.0",
    "logicalId": "00000000-0000-0000-0000-000000000000"
  }
}
""" % MODEL_NAME


def read_env(repo_root: Path) -> dict:
    env = {}
    f = repo_root / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    env = read_env(repo_root)
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=env.get("FABRIC_WORKSPACE_ID"))
    ap.add_argument("--lakehouse", default=env.get("FABRIC_LAKEHOUSE_ID"))
    ap.add_argument("--out", default=str(Path(__file__).with_name(f"{MODEL_NAME}.SemanticModel")))
    args = ap.parse_args()

    if not args.workspace or not args.lakehouse:
        raise SystemExit("FABRIC_WORKSPACE_ID and FABRIC_LAKEHOUSE_ID must be set (in .env or via --workspace/--lakehouse).")

    root = Path(args.out)
    defn = root / "definition"
    tables = defn / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    def w(path: Path, text: str):
        path.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", path.relative_to(root.parent))

    w(root / "definition.pbism", PBISM)
    w(root / ".platform", PLATFORM)
    w(defn / "database.tmdl", DATABASE)
    w(defn / "model.tmdl", model_tmdl())
    w(defn / "expressions.tmdl", expressions_tmdl(args.workspace, args.lakehouse))
    w(defn / "relationships.tmdl", relationships_tmdl())
    for tname in COLS:
        w(tables / f"{tname}.tmdl", table_tmdl(tname))

    print(f"\nDirect Lake model '{MODEL_NAME}' TMDL generated at {root}")
    print(f"OneLake source: workspace={args.workspace} lakehouse={args.lakehouse} schema={SCHEMA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
