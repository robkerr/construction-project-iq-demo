#!/usr/bin/env python
"""Generate the PBIR definition for the **Portfolio Schedule Risk** Power BI report (Phase 5).

Emits a `ProjectControlsIQ.Report/` folder in the enhanced report (PBIR) format that binds
`byConnection` to the ProjectControlsIQ semantic model (Phase 3) and lays out the single-page
"Portfolio Schedule Risk" dashboard described in powerbi/schedule_risk_dashboard.md:

  * KPI band (4 cards)           -- Projects At Risk / Worst Schedule Risk / Forecast Overrun / Late POs
  * Hero risk-ranked bar         -- project_name x Schedule Risk Score (Falcon #1, Red)
  * 8 cross-system driver tiles  -- 4 non-SAP (schedule) + 4 SAP (cost/procurement)
  * WBS driver detail table
  * 4 slicers                    -- region / client / supplier risk_rating / contract_type

The semantic-model id is read from the repo `.env` (SEMANTIC_MODEL_ID) or --model-id. Deploy the
emitted folder with scripts/31_deploy_report.ps1.

NOTE: report/visual authoring is not covered by the Fabric modeling MCP, so this is a best-effort,
API-deployable scaffold. Every measure/column binding is real; fine-tune visuals in the service.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REPORT_NAME = "ProjectControlsIQ"
PAGE_ID = "portfolioScheduleRisk"
PAGE_NAME = "Portfolio Schedule Risk"
PAGE_W, PAGE_H = 1280, 720

S_REPORT = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.1.0/schema.json"
S_VERSION = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
S_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json"
S_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json"
S_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.4.0/schema.json"
S_PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"

PLATFORM = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
    "metadata": {"type": "Report", "displayName": REPORT_NAME},
    "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000000"},
}


# ---------------------------------------------------------------- field helpers
def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field: dict, entity: str, prop: str) -> dict:
    return {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def pos(x, y, w, h, z=0, tab=0) -> dict:
    return {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": tab}


def title_objs(text: str) -> dict:
    esc = text.replace("'", "''")
    return {
        "title": [{
            "properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}},
                "text": {"expr": {"Literal": {"Value": f"'{esc}'"}}},
            }
        }]
    }


# --------------------------------------------------------------- visual builders
def card(name, position, entity, measure, title) -> dict:
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "card",
            "query": {"queryState": {"Values": {"projections": [proj(meas(entity, measure), entity, measure)]}}},
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def hero_bar(name, position) -> dict:
    cat = proj(col("dim_project", "project_name"), "dim_project", "project_name")
    val = proj(meas("dim_project", "Schedule Risk Score"), "dim_project", "Schedule Risk Score")
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "clusteredBarChart",
            "query": {
                "queryState": {
                    "Category": {"projections": [cat]},
                    "Y": {"projections": [val]},
                },
                "sortDefinition": {
                    "sort": [{"field": meas("dim_project", "Schedule Risk Score"), "direction": "Descending"}]
                },
            },
            "objects": title_objs("Schedule Risk Score by Project"),
            "drillFilterOtherVisuals": True,
        },
    }


def detail_table(name, position) -> dict:
    fields = [
        proj(col("dim_wbs", "wbs_name"), "dim_wbs", "wbs_name"),
        proj(col("dim_wbs", "discipline"), "dim_wbs", "discipline"),
        proj(col("dim_wbs", "origin_system"), "dim_wbs", "origin_system"),
        proj(meas("fact_schedule_activity", "Critical Path At Risk"), "fact_schedule_activity", "Critical Path At Risk"),
        proj(meas("fact_schedule_activity", "Min Total Float (days)"), "fact_schedule_activity", "Min Total Float (days)"),
        proj(meas("sap_mm_po", "Late Long-Lead POs"), "sap_mm_po", "Late Long-Lead POs"),
        proj(meas("sap_fi_cost", "Forecast Overrun"), "sap_fi_cost", "Forecast Overrun"),
    ]
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "tableEx",
            "query": {"queryState": {"Values": {"projections": fields}}},
            "objects": title_objs("WBS driver detail (select a project)"),
            "drillFilterOtherVisuals": True,
        },
    }


def slicer(name, position, entity, column, title) -> dict:
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(col(entity, column), entity, column)]}}},
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def build_visuals() -> list[dict]:
    v = []
    # --- KPI band (y=16, h=96) ---
    v.append(card("kpiProjectsAtRisk", pos(16, 16, 296, 96, tab=1), "dim_project", "Projects At Risk", "Projects At Risk"))
    v.append(card("kpiWorstRisk", pos(328, 16, 296, 96, tab=2), "dim_project", "Worst Schedule Risk", "Worst Schedule Risk"))
    v.append(card("kpiForecastOverrun", pos(640, 16, 296, 96, tab=3), "dim_project", "Total Forecast Overrun", "Total Forecast Overrun (SAP)"))
    v.append(card("kpiLatePOs", pos(952, 16, 296, 96, tab=4), "dim_project", "Total Late Long-Lead POs", "Late Long-Lead POs (SAP)"))

    # --- Hero risk-ranked bar (left) ---
    v.append(hero_bar("heroRiskBar", pos(16, 124, 536, 396, tab=5)))

    # --- Cross-system driver tiles (right rail): 2 cols x 4 rows ---
    ns_col, sap_col, w = 568, 924, 340
    rows = [124, 226, 328, 430]
    non_sap = [
        ("fact_schedule_activity", "Schedule Slip (days)", "Non-SAP \u00b7 Schedule Slip (days)"),
        ("fact_schedule_activity", "Critical Path At Risk", "Non-SAP \u00b7 Critical Path At Risk"),
        ("fact_schedule_activity", "Min Total Float (days)", "Non-SAP \u00b7 Min Total Float (days)"),
        ("fact_engineering_change", "Approved EC Schedule Impact (days)", "Non-SAP \u00b7 Approved EC Impact (days)"),
    ]
    sap = [
        ("sap_fi_cost", "Forecast Overrun", "SAP \u00b7 Forecast Overrun"),
        ("sap_fi_cost", "Cost To Complete", "SAP \u00b7 Cost To Complete"),
        ("sap_mm_po", "Late Long-Lead POs", "SAP \u00b7 Late Long-Lead POs"),
        ("sap_fi_cost", "Earned Value", "SAP \u00b7 Earned Value"),
    ]
    tab = 6
    for i, (ent, m, t) in enumerate(non_sap):
        v.append(card(f"tileNs{i}", pos(ns_col, rows[i], w, 90, tab=tab), ent, m, t)); tab += 1
    for i, (ent, m, t) in enumerate(sap):
        v.append(card(f"tileSap{i}", pos(sap_col, rows[i], w, 90, tab=tab), ent, m, t)); tab += 1

    # --- WBS driver detail table (bottom-left) ---
    v.append(detail_table("wbsDetail", pos(16, 532, 920, 172, tab=tab))); tab += 1

    # --- Slicers (bottom-right column) ---
    v.append(slicer("slcRegion", pos(952, 532, 312, 40, tab=tab), "dim_project", "region", "Region")); tab += 1
    v.append(slicer("slcClient", pos(952, 576, 312, 40, tab=tab), "dim_project", "client", "Client")); tab += 1
    v.append(slicer("slcSupplierRisk", pos(952, 620, 312, 40, tab=tab), "sap_supplier", "risk_rating", "Supplier risk rating (SAP)")); tab += 1
    v.append(slicer("slcContract", pos(952, 664, 312, 40, tab=tab), "dim_project", "contract_type", "Contract type")); tab += 1
    return v


def read_env(repo_root: Path) -> dict:
    env, f = {}, repo_root / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, val = line.split("=", 1)
                env[k.strip()] = val.strip()
    return env


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    env = read_env(repo_root)
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default=env.get("SEMANTIC_MODEL_ID"))
    ap.add_argument("--out", default=str(Path(__file__).with_name(f"{REPORT_NAME}.Report")))
    args = ap.parse_args()
    if not args.model_id:
        raise SystemExit("SEMANTIC_MODEL_ID must be set (in .env or via --model-id). Run scripts/30_deploy_semantic_model.ps1 first.")

    root = Path(args.out)
    defn = root / "definition"
    pagedir = defn / "pages" / PAGE_ID
    (pagedir / "visuals").mkdir(parents=True, exist_ok=True)

    def w(path: Path, obj):
        text = obj if isinstance(obj, str) else json.dumps(obj, indent=2)
        path.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", path.relative_to(root.parent))

    # report-level
    w(root / ".platform", PLATFORM)
    w(root / "definition.pbir", {
        "$schema": S_PBIR,
        "version": "4.0",
        "datasetReference": {"byConnection": {"connectionString": f"semanticmodelid={args.model_id}"}},
    })
    w(defn / "version.json", {"$schema": S_VERSION, "version": "4.0.0"})
    w(defn / "report.json", {
        "$schema": S_REPORT,
        "themeCollection": {"baseTheme": {
            "name": "CY24SU10",
            "reportVersionAtImport": {"page": "1.0.0", "report": "3.1.0", "visual": "1.4.0"},
            "type": "SharedResources",
        }},
    })

    # pages
    w(defn / "pages" / "pages.json", {"$schema": S_PAGES, "pageOrder": [PAGE_ID], "activePageName": PAGE_ID})
    w(pagedir / "page.json", {
        "$schema": S_PAGE,
        "name": PAGE_ID,
        "displayName": PAGE_NAME,
        "displayOption": "FitToPage",
        "height": PAGE_H,
        "width": PAGE_W,
    })

    # visuals
    for vis in build_visuals():
        vdir = pagedir / "visuals" / vis["name"]
        vdir.mkdir(parents=True, exist_ok=True)
        w(vdir / "visual.json", vis)

    print(f"\nReport '{REPORT_NAME}' PBIR generated at {root}")
    print(f"Bound byConnection to semantic model {args.model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
