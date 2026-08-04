#!/usr/bin/env python3
"""
build_local_report.py — author the EPCDemo report pages (PBIR) for the local,
self-contained PBIP.

Unlike the earlier ``build_report.py`` / ``build_bid_report.py`` (which emitted the
*old* PBIR schema — visual 1.4.0 — and bound ``byConnection`` for REST deployment to
the Fabric service), this script writes pages in the **modern** PBIR schema that
Power BI Desktop authored the EPCDemo shell with (visual 2.12.0 / page 2.3.1) and
leaves the Desktop-generated ``report.json``, ``definition.pbir`` (byPath), theme,
and ``version.json`` untouched. That combination is what actually opens cleanly in
Desktop.

Two pages, each designed for the "spot the issue on the dashboard -> open Copilot in
another window to dig in" demo flow (each page carries an explicit Copilot callout):

  1. Portfolio Schedule Risk   -> hero: Project Falcon is the #1 schedule risk
  2. Bid Evaluation (TBE / CBE) -> hero: cheapest bid disqualified, best-value award

Run:  python powerbi/build_local_report.py
Then reload EPCDemo.pbip in Power BI Desktop.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFN = REPO / "powerbi" / "EPCDemo.Report" / "definition"
PAGES = DEFN / "pages"

PAGE_W, PAGE_H = 1920, 1080

S_VISUAL = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.12.0/schema.json"
S_PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.3.1/schema.json"
S_PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"


# ---------------------------------------------------------------- field helpers
def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def agg(entity: str, prop: str, func: int = 1) -> dict:
    """Aggregated column field (func 1 = Average). Azure Maps requires lat/lon to be
    aggregated when a Location field is also present."""
    return {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}, "Function": func}}


def proj(field: dict, entity: str, prop: str) -> dict:
    return {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def proj_avg(entity: str, prop: str) -> dict:
    return {"field": agg(entity, prop, 1), "queryRef": f"Average({entity}.{prop})", "nativeQueryRef": f"Average of {prop}"}


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


def bar(name, position, cat_entity, cat_col, val_specs, title, sort_entity, sort_meas, sort_dir="Descending") -> dict:
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
                "sortDefinition": {"sort": [{"field": meas(sort_entity, sort_meas), "direction": sort_dir}]},
            },
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def table(name, position, fields, title, sort_field=None, sort_dir="Ascending", filters=None) -> dict:
    """fields: list of (entity, prop, is_measure)."""
    projs = [proj((meas(e, p) if m else col(e, p)), e, p) for (e, p, m) in fields]
    q = {"queryState": {"Values": {"projections": projs}}}
    if sort_field is not None:
        se, sp, sm = sort_field
        q["sortDefinition"] = {"sort": [{"field": (meas(se, sp) if sm else col(se, sp)), "direction": sort_dir}]}
    vis = {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "tableEx",
            "query": q,
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }
    if filters:
        vis["filterConfig"] = {"filters": filters}
    return vis


def catfilter(entity: str, prop: str, values: list) -> dict:
    """Applied categorical visual-level filter: entity[prop] IN values.

    `values` are literal expressions already formatted for the query language —
    strings as "'Late'" (single-quoted), booleans as "true"/"false".
    """
    return {
        "name": f"flt_{entity}_{prop}",
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": entity, "Type": 0}],
            "Where": [{
                "Condition": {
                    "In": {
                        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": prop}}],
                        "Values": [[{"Literal": {"Value": v}}] for v in values],
                    }
                }
            }],
        },
    }


def matrix(name, position, rows, cols, vals, title) -> dict:
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "pivotTable",
            "query": {
                "queryState": {
                    "Rows": {"projections": [proj(col(*rows), *rows)]},
                    "Columns": {"projections": [proj(col(*cols), *cols)]},
                    "Values": {"projections": [proj(meas(*vals), *vals)]},
                }
            },
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def donut(name, position, cat_entity, cat_col, val_entity, val_meas, title) -> dict:
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "donutChart",
            "query": {
                "queryState": {
                    "Category": {"projections": [proj(col(cat_entity, cat_col), cat_entity, cat_col)]},
                    "Y": {"projections": [proj(meas(val_entity, val_meas), val_entity, val_meas)]},
                }
            },
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def map_bubble(name, position, location, lat, lon, size_spec, legend, tooltip_specs, title) -> dict:
    """Native Azure Maps bubble layer. location = (entity, col) supplies the Category /
    Location bucket so every bubble has a selection identity (required — without it the
    Azure Maps click handler throws 'handleClearSelection' and the report fails to render).
    lat/lon = (entity, col) provide precise positioning; size_spec/legend = (entity, name);
    tooltip_specs = list of (entity, prop, is_measure)."""
    ce, cc = location
    le, lc = lat
    oe, oc = lon
    se, sm = size_spec
    ge, gc = legend
    tips = [proj((meas(e, p) if m else col(e, p)), e, p) for (e, p, m) in tooltip_specs]
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "azureMap",
            "query": {
                "queryState": {
                    "Category": {"projections": [proj(col(ce, cc), ce, cc)]},
                    "Y": {"projections": [proj_avg(le, lc)]},
                    "X": {"projections": [proj_avg(oe, oc)]},
                    "Size": {"projections": [proj(meas(se, sm), se, sm)]},
                    "Series": {"projections": [proj(col(ge, gc), ge, gc)]},
                    "Tooltips": {"projections": tips},
                }
            },
            "objects": title_objs(title),
            "drillFilterOtherVisuals": True,
        },
    }


def slicer(name, position, entity, column, title) -> dict:
    objs = title_objs(title)
    # render as a dropdown so users see there are choices (list mode hides options)
    objs["data"] = [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "slicer",
            "query": {"queryState": {"Values": {"projections": [proj(col(entity, column), entity, column)]}}},
            "objects": objs,
            "drillFilterOtherVisuals": True,
        },
    }


def textbox(name, position, runs) -> dict:
    """runs: list of (text, textStyle_dict)."""
    return {
        "$schema": S_VISUAL,
        "name": name,
        "position": position,
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [{
                    "properties": {
                        "paragraphs": [{
                            "textRuns": [{"value": t, "textStyle": s} for (t, s) in runs]
                        }]
                    }
                }]
            },
        },
    }


H1 = {"fontSize": "22pt", "fontWeight": "bold"}
CALLOUT_HDR = {"fontSize": "13pt", "fontWeight": "bold"}
CALLOUT_BODY = {"fontSize": "11pt"}
GROUP_HDR = {"fontSize": "12pt", "fontWeight": "bold"}


# --------------------------------------------------------------- page 0: executive overview
def page_executive() -> list[dict]:
    v = []
    v.append(textbox("p0Title", pos(24, 16, 1120, 56, tab=0),
                     [("Executive Portfolio Overview", H1)]))
    v.append(textbox("p0Copilot", pos(1160, 16, 736, 104, tab=1), [
        ("\u26a0 Ask Copilot\n", CALLOUT_HDR),
        ("One project is trending Red on schedule. Click the largest red-flagged bubble, then open "
         "the agent and ask: \u201cWhich project is most at risk right now, and why?\u201d", CALLOUT_BODY),
    ]))

    # KPI band
    v.append(card("p0KpiActive", pos(24, 132, 456, 120, tab=2), "dim_project", "Active Projects", "Active Projects"))
    v.append(card("p0KpiPct", pos(496, 132, 456, 120, tab=3), "dim_project", "Avg % Complete", "Avg % Complete"))
    v.append(card("p0KpiAtRisk", pos(968, 132, 456, 120, tab=4), "dim_project", "Projects At Risk", "Projects At Risk"))
    v.append(card("p0KpiOverrun", pos(1440, 132, 456, 120, tab=5), "dim_project", "Total Forecast Overrun", "Forecast Overrun (SAP)"))

    # map (left) — global portfolio, bubble size = project financial size, color by region
    v.append(map_bubble("p0Map", pos(24, 280, 1160, 560, tab=6),
                        ("dim_project", "city"),
                        ("dim_project", "latitude"), ("dim_project", "longitude"),
                        ("sap_fi_cost", "Earned Value"), ("dim_project", "region"),
                        [("dim_project", "project_name", False),
                         ("dim_project", "Risk Band", True),
                         ("dim_project", "Schedule Risk Score", True),
                         ("dim_project", "Avg % Complete", True)],
                        "Portfolio map \u00b7 bubble size = earned value, color = region"))

    # right column: donut (portfolio mix) + % complete bar
    v.append(donut("p0RegionDonut", pos(1208, 280, 688, 270, tab=7),
                   "dim_project", "region", "dim_project", "Active Projects",
                   "Active projects by region"))
    v.append(bar("p0PctBar", pos(1208, 566, 688, 274, tab=8),
                 "dim_project", "project_name",
                 [("dim_project", "Avg % Complete")],
                 "% complete by project",
                 "dim_project", "Avg % Complete"))

    # bottom: schedule-risk bar across the full portfolio (the "spot the issue" hook)
    v.append(bar("p0RiskBar", pos(24, 856, 1872, 200, tab=9),
                 "dim_project", "project_name",
                 [("dim_project", "Schedule Risk Score")],
                 "Schedule Risk Score by project (Red = act now)",
                 "dim_project", "Schedule Risk Score"))
    return v


# --------------------------------------------------------------- page 1: schedule risk
def page_schedule_risk() -> list[dict]:
    v = []
    v.append(textbox("p1Title", pos(24, 16, 1120, 56, tab=0),
                     [("Portfolio Schedule Risk", H1)]))
    v.append(textbox("p1Copilot", pos(1160, 16, 736, 104, tab=1), [
        ("\u26a0 Ask Copilot\n", CALLOUT_HDR),
        ("The dashboard shows the ", CALLOUT_BODY),
        ("what", {"fontSize": "11pt", "fontWeight": "bold"}),
        (". Open the agent and ask the cross-system ", CALLOUT_BODY),
        ("so-what", {"fontSize": "11pt", "fontWeight": "bold"}),
        (": \u201cWhat\u2019s driving Falcon\u2019s schedule risk, and what does the late transformer "
         "PO mean for our sourcing and live field risk?\u201d", CALLOUT_BODY),
    ]))

    # slicer strip
    v.append(slicer("p1SlcRegion", pos(24, 132, 456, 64, tab=2), "dim_project", "region", "Region"))
    v.append(slicer("p1SlcClient", pos(496, 132, 456, 64, tab=3), "dim_project", "client", "Client"))
    v.append(slicer("p1SlcContract", pos(968, 132, 456, 64, tab=4), "dim_project", "contract_type", "Contract type"))
    v.append(slicer("p1SlcSupplierRisk", pos(1440, 132, 456, 64, tab=5), "sap_supplier", "risk_rating", "Supplier risk (SAP)"))

    # KPI band
    v.append(card("p1KpiAtRisk", pos(24, 212, 456, 120, tab=6), "dim_project", "Projects At Risk", "Projects At Risk"))
    v.append(card("p1KpiWorst", pos(496, 212, 456, 120, tab=7), "dim_project", "Worst Schedule Risk", "Worst Schedule Risk"))
    v.append(card("p1KpiOverrun", pos(968, 212, 456, 120, tab=8), "dim_project", "Total Forecast Overrun", "Total Forecast Overrun (SAP)"))
    v.append(card("p1KpiLatePo", pos(1440, 212, 456, 120, tab=9), "dim_project", "Total Late Long-Lead POs", "Late Long-Lead POs (SAP)"))

    # hero bar
    v.append(bar("p1HeroBar", pos(24, 348, 1160, 420, tab=10),
                 "dim_project", "project_name",
                 [("dim_project", "Schedule Risk Score")],
                 "Schedule Risk Score by project (Falcon = #1)",
                 "dim_project", "Schedule Risk Score"))

    # right-rail driver tiles
    v.append(textbox("p1NonSapHdr", pos(1208, 348, 336, 32, tab=11), [("Non-SAP \u00b7 Schedule", GROUP_HDR)]))
    v.append(textbox("p1SapHdr", pos(1560, 348, 336, 32, tab=12), [("SAP \u00b7 Cost & Procurement", GROUP_HDR)]))
    nonsap = [
        ("Schedule Slip (days)", "fact_schedule_activity", "Schedule Slip (days)"),
        ("Critical Path At Risk", "fact_schedule_activity", "Critical Path At Risk"),
        ("Min Total Float (days)", "fact_schedule_activity", "Min Total Float (days)"),
        ("Approved EC Impact (days)", "fact_engineering_change", "Approved EC Schedule Impact (days)"),
    ]
    sap = [
        ("Forecast Overrun", "sap_fi_cost", "Forecast Overrun"),
        ("Cost To Complete", "sap_fi_cost", "Cost To Complete"),
        ("Late Long-Lead POs", "sap_mm_po", "Late Long-Lead POs"),
        ("Earned Value", "sap_fi_cost", "Earned Value"),
    ]
    y0, ch, gap = 388, 88, 8
    for i, (title, ent, m) in enumerate(nonsap):
        v.append(card(f"p1NonSap{i}", pos(1208, y0 + i * (ch + gap), 336, ch, tab=13 + i), ent, m, title))
    for i, (title, ent, m) in enumerate(sap):
        v.append(card(f"p1Sap{i}", pos(1560, y0 + i * (ch + gap), 336, ch, tab=17 + i), ent, m, title))

    # Root-cause band (bottom): "Why Falcon is red" — names EC-1207 + PO-00510 on the same WBS.
    # Select Falcon in the hero bar and both tables resolve the SAME dim_wbs[wbs_name],
    # so the collision (one work package, two systems) is shown by name, not inferred.
    v.append(textbox("p1RootCauseHdr", pos(24, 784, 1872, 40, tab=21), [
        ("Why Falcon is red \u2014 root cause:  ", GROUP_HDR),
        ("select Project Falcon in the risk bar \u2014 the SAME work package (WBS) carries BOTH a "
         "schedule slip (Primavera change control) and a late long-lead transformer PO (SAP).",
         {"fontSize": "12pt"}),
    ]))
    v.append(table("p1EcRootCause", pos(24, 832, 920, 224, tab=22), [
        ("fact_engineering_change", "ec_id", False),
        ("dim_wbs", "wbs_name", False),
        ("fact_engineering_change", "schedule_impact_days", False),
        ("fact_engineering_change", "title", False),
    ], "Schedule driver \u2014 approved engineering change (Primavera)",
        sort_field=("fact_engineering_change", "schedule_impact_days", False), sort_dir="Descending",
        filters=[catfilter("fact_engineering_change", "status", ["'Approved'"])]))
    v.append(table("p1PoRootCause", pos(976, 832, 920, 224, tab=23), [
        ("sap_mm_po", "po_id", False),
        ("dim_wbs", "wbs_name", False),
        ("sap_mm_po", "material_desc", False),
        ("sap_supplier", "supplier_name", False),
        ("sap_mm_po", "status", False),
    ], "Procurement driver \u2014 late long-lead PO (SAP)",
        sort_field=("sap_mm_po", "status", False), sort_dir="Descending",
        filters=[
            catfilter("sap_mm_po", "is_long_lead", ["true"]),
            catfilter("sap_mm_po", "status", ["'Late'"]),
        ]))
    return v


# --------------------------------------------------------------- page 2: bid evaluation
def page_bid_eval() -> list[dict]:
    v = []
    v.append(textbox("p2Title", pos(24, 16, 1120, 56, tab=0),
                     [("Bid Evaluation \u2014 Technical & Commercial (TBE / CBE)", H1)]))
    v.append(textbox("p2Copilot", pos(1160, 16, 736, 104, tab=1), [
        ("\u26a0 Ask Copilot\n", CALLOUT_HDR),
        ("The cheapest bid was disqualified on technical grounds. Open the agent and ask: "
         "\u201cGenerate the technical and commercial bid evaluation for RFQ-0001.\u201d", CALLOUT_BODY),
    ]))

    # slicer strip
    v.append(slicer("p2SlcTag", pos(24, 132, 456, 64, tab=2), "dim_rfq", "equipment_tag", "RFQ / equipment tag"))
    v.append(slicer("p2SlcCat", pos(496, 132, 456, 64, tab=3), "dim_rfq", "material_category", "Material category"))
    v.append(slicer("p2SlcProject", pos(968, 132, 456, 64, tab=4), "dim_project", "project_name", "Project"))
    v.append(slicer("p2SlcRisk", pos(1440, 132, 456, 64, tab=5), "sap_supplier", "risk_rating", "Supplier risk (SAP)"))

    # KPI band
    v.append(card("p2KpiBids", pos(24, 212, 456, 120, tab=6), "fact_bid", "Bid Count", "Bids Received"))
    v.append(card("p2KpiQual", pos(496, 212, 456, 120, tab=7), "fact_bid", "Qualified Bids", "Technically Qualified"))
    v.append(card("p2KpiLowQuote", pos(968, 212, 456, 120, tab=8), "fact_bid", "Lowest Quoted Price", "Lowest Quoted Price"))
    v.append(card("p2KpiRecommend", pos(1440, 212, 456, 120, tab=9), "fact_bid", "Recommended Evaluated Price", "Recommended Award (evaluated)"))

    # TBE + CBE bars
    v.append(bar("p2TbeBar", pos(24, 348, 928, 288, tab=10),
                 "fact_bid", "supplier_name",
                 [("fact_bid", "Avg Technical Score")],
                 "TBE \u00b7 Technical score by supplier",
                 "fact_bid", "Avg Technical Score"))
    v.append(bar("p2CbeBar", pos(968, 348, 928, 288, tab=11),
                 "fact_bid", "supplier_name",
                 [("fact_bid", "Quoted Price"), ("fact_bid", "Evaluated Price")],
                 "CBE \u00b7 Quoted vs evaluated price by supplier",
                 "fact_bid", "Evaluated Price", sort_dir="Descending"))

    # bid comparison table (bottom-left)
    v.append(table("p2BidTable", pos(24, 652, 928, 404, tab=12), [
        ("fact_bid", "supplier_name", False),
        ("fact_bid", "Avg Technical Score", True),
        ("fact_bid", "tbe_status", False),
        ("fact_bid", "Quoted Price", True),
        ("fact_bid", "Evaluated Price", True),
        ("fact_bid", "award_status", False),
    ], "Bid comparison (sorted by evaluated price)",
        sort_field=("fact_bid", "Evaluated Price", True), sort_dir="Ascending"))

    # compliance matrix (bottom-right) + award cards
    v.append(matrix("p2Compliance", pos(968, 652, 928, 280, tab=13),
                    ("dim_tech_requirement", "requirement"),
                    ("fact_bid", "supplier_name"),
                    ("fact_bid_tech_eval", "Exception Items"),
                    "Technical compliance \u00b7 exceptions by requirement \u00d7 supplier"))
    v.append(card("p2CardRecSupplier", pos(968, 948, 456, 108, tab=14), "fact_bid", "Recommended Supplier", "Recommended supplier"))
    v.append(card("p2CardEvalDelta", pos(1440, 948, 456, 108, tab=15), "fact_bid", "Evaluated vs Lowest Quote", "Premium over lowest quote"))
    return v


PAGE_DEFS = [
    ("executive", "Executive Portfolio Overview", page_executive),
    ("scheduleRisk", "Portfolio Schedule Risk", page_schedule_risk),
    ("bidEvaluation", "Bid Evaluation (TBE / CBE)", page_bid_eval),
]


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8", newline="\n")


def main() -> None:
    if not DEFN.exists():
        raise SystemExit(f"Report definition not found at {DEFN}")

    # remove any existing page folders (keep pages.json parent dir)
    for child in PAGES.iterdir():
        if child.is_dir():
            shutil.rmtree(child)

    order = [pid for (pid, _n, _f) in PAGE_DEFS]
    write_json(PAGES / "pages.json", {"$schema": S_PAGES, "pageOrder": order, "activePageName": order[0]})

    for pid, name, fn in PAGE_DEFS:
        pdir = PAGES / pid
        (pdir / "visuals").mkdir(parents=True, exist_ok=True)
        write_json(pdir / "page.json", {
            "$schema": S_PAGE,
            "name": pid,
            "displayName": name,
            "displayOption": "FitToPage",
            "height": PAGE_H,
            "width": PAGE_W,
        })
        vis = fn()
        for vjson in vis:
            vdir = pdir / "visuals" / vjson["name"]
            vdir.mkdir(parents=True, exist_ok=True)
            write_json(vdir / "visual.json", vjson)
        print(f"page '{name}' ({pid}): {len(vis)} visuals")

    print(f"\nAuthored {len(PAGE_DEFS)} pages into {PAGES}")


if __name__ == "__main__":
    main()
