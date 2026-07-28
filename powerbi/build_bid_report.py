#!/usr/bin/env python
"""Generate the PBIR definition for the **Bid Evaluation (TBE / CBE)** Power BI report.

Emits a `BidEvaluationIQ.Report/` folder in the enhanced report (PBIR) format that binds
`byConnection` to the same ProjectControlsIQ semantic model and lays out a single-page
procurement bid-evaluation dashboard for the two use cases:

  * Technical Bid Evaluation (TBE) -- per-supplier weighted technical score + compliance matrix
  * Commercial Bid Evaluation (CBE) -- normalized evaluated-price comparison + award recommendation

Layout (1280x720):
  * KPI band (4 cards)      -- Bid Count / Qualified Bids / Lowest Quoted Price / Recommended Evaluated Price
  * TBE bar (left)          -- Avg Technical Score by supplier
  * CBE bar (right)         -- Quoted vs Evaluated Price by supplier
  * Bid comparison table    -- supplier x quoted / evaluated / score / status / award
  * Technical compliance    -- requirement x supplier x compliance (matrix)
  * Recommended-supplier card + 4 slicers (RFQ / category / project / supplier risk)

Deploy with scripts/31_deploy_report.ps1 -ReportName BidEvaluationIQ
    -DefinitionRoot powerbi/BidEvaluationIQ.Report -ReportIdKey BID_REPORT_ID -ReportNameKey BID_REPORT_NAME

NOTE: report/visual authoring is not covered by the Fabric modeling MCP, so this is a best-effort,
API-deployable scaffold. Every measure/column binding is real; fine-tune visuals in the service.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REPORT_NAME = "BidEvaluationIQ"
PAGE_ID = "bidEvaluation"
PAGE_NAME = "Bid Evaluation (TBE / CBE)"
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


def bar(name, position, cat_entity, cat_col, val_specs, title, sort_entity, sort_meas) -> dict:
    cat = proj(col(cat_entity, cat_col), cat_entity, cat_col)
    y_proj = [proj(meas(e, m), e, m) for (e, m) in val_specs]
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "clusteredBarChart",
            "query": {
                "queryState": {
                    "Category": {"projections": [cat]},
                    "Y": {"projections": y_proj},
                },
                "sortDefinition": {
                    "sort": [{"field": meas(sort_entity, sort_meas), "direction": "Descending"}]
                },
            },
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def bid_table(name, position) -> dict:
    fields = [
        proj(col("fact_bid", "supplier_name"), "fact_bid", "supplier_name"),
        proj(meas("fact_bid", "Avg Technical Score"), "fact_bid", "Avg Technical Score"),
        proj(col("fact_bid", "tbe_status"), "fact_bid", "tbe_status"),
        proj(meas("fact_bid", "Quoted Price"), "fact_bid", "Quoted Price"),
        proj(meas("fact_bid", "Evaluated Price"), "fact_bid", "Evaluated Price"),
        proj(col("fact_bid", "delivery_weeks"), "fact_bid", "delivery_weeks"),
        proj(col("fact_bid", "award_status"), "fact_bid", "award_status"),
    ]
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {"Values": {"projections": fields}},
                "sortDefinition": {
                    "sort": [{"field": meas("fact_bid", "Evaluated Price"), "direction": "Ascending"}]
                },
            },
            "objects": title_objs("Bid comparison (sorted by evaluated price)"),
            "drillFilterOtherVisuals": True,
        },
    }


def compliance_matrix(name, position) -> dict:
    rows = proj(col("dim_tech_requirement", "requirement"), "dim_tech_requirement", "requirement")
    cols = proj(col("fact_bid_tech_eval", "supplier_id"), "fact_bid_tech_eval", "supplier_id")
    val = proj(meas("fact_bid_tech_eval", "Compliance Items"), "fact_bid_tech_eval", "Compliance Items")
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "pivotTable",
            "query": {
                "queryState": {
                    "Rows": {"projections": [rows]},
                    "Columns": {"projections": [cols]},
                    "Values": {"projections": [val]},
                }
            },
            "objects": title_objs("Technical compliance matrix (requirement x supplier)"),
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
    # --- KPI band (y=16, h=88) ---
    v.append(card("kpiBidCount", pos(16, 16, 296, 88, tab=1), "fact_bid", "Bid Count", "Bids Received"))
    v.append(card("kpiQualified", pos(328, 16, 296, 88, tab=2), "fact_bid", "Qualified Bids", "Technically Qualified"))
    v.append(card("kpiLowestQuote", pos(640, 16, 296, 88, tab=3), "fact_bid", "Lowest Quoted Price", "Lowest Quoted Price"))
    v.append(card("kpiRecommended", pos(952, 16, 296, 88, tab=4), "fact_bid", "Recommended Evaluated Price", "Recommended Award (evaluated)"))

    # --- Slicer strip (y=112, h=48) ---
    v.append(slicer("slcRfq", pos(16, 112, 296, 48, tab=5), "dim_rfq", "equipment_tag", "RFQ / equipment tag"))
    v.append(slicer("slcCategory", pos(328, 112, 296, 48, tab=6), "dim_rfq", "material_category", "Material category"))
    v.append(slicer("slcProject", pos(640, 112, 296, 48, tab=7), "dim_project", "project_name", "Project"))
    v.append(slicer("slcSupplierRisk", pos(952, 112, 296, 48, tab=8), "sap_supplier", "risk_rating", "Supplier risk rating (SAP)"))

    # --- TBE bar (left) + CBE bar (right) ---
    v.append(bar("tbeScoreBar", pos(16, 168, 616, 232, tab=9),
                 "fact_bid", "supplier_name",
                 [("fact_bid", "Avg Technical Score")],
                 "TBE \u00b7 Technical Score by supplier",
                 "fact_bid", "Avg Technical Score"))
    v.append(bar("cbePriceBar", pos(648, 168, 616, 232, tab=10),
                 "fact_bid", "supplier_name",
                 [("fact_bid", "Quoted Price"), ("fact_bid", "Evaluated Price")],
                 "CBE \u00b7 Quoted vs Evaluated price by supplier",
                 "fact_bid", "Evaluated Price"))

    # --- Bid comparison table (bottom-left) ---
    v.append(bid_table("bidTable", pos(16, 408, 616, 296, tab=11)))

    # --- Technical compliance matrix (bottom-right) ---
    v.append(compliance_matrix("complianceMatrix", pos(648, 408, 616, 210, tab=12)))

    # --- Recommended supplier + evaluated-premium cards ---
    v.append(card("cardRecSupplier", pos(648, 624, 300, 80, tab=13), "fact_bid", "Recommended Supplier", "Recommended supplier"))
    v.append(card("cardEvalDelta", pos(964, 624, 300, 80, tab=14), "fact_bid", "Evaluated vs Lowest Quote", "Evaluated premium vs lowest quote"))
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
