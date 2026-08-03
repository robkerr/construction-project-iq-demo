#!/usr/bin/env python3
"""Generate the Semantic Model scenario diagram (SVG + PNG).

Left-to-right business-analysis pipeline for the EPC demo's first scenario
(Maya's morning): one governed Fabric semantic model (ProjectControlsIQ) drives
DAX measures -> a Power BI dashboard -> an LLM-based Q&A (Copilot) that answers
an ad-hoc question and generates the MPR. Every stage resolves to the same
model, so the KPI card, the drill-down, and the Copilot answer all compute the
same Schedule Risk Score.
"""
import os

W, H = 1720, 900
DARK = "#1f2430"
GRAY = "#5b6472"

# ---------------------------------------------------------------- primitives --
def rr(x, y, w, h, fill="#ffffff", stroke="#c9d2de", sw=1.6, rx=12,
       dash=None, shadow=False, opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    f = ' filter="url(#sh)"' if shadow else ''
    o = f' fill-opacity="{opacity}"' if opacity is not None else ''
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'
            f' stroke="{stroke}" stroke-width="{sw}"{d}{f}{o}/>')


def txt(x, y, s, size=14, w=400, anchor="middle", fill=DARK, italic=False, mono=False):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fam = "Consolas, 'DejaVu Sans Mono', monospace" if mono else 'Segoe UI, Arial, sans-serif'
    it = ' font-style="italic"' if italic else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" '
            f'text-anchor="{anchor}" fill="{fill}" font-family="{fam}"{it}>{s}</text>')


def flow_arrow(gx, cy, label, color="#7f8ca0"):
    x = gx
    pts = (f"{x-24},{cy-9} {x+4},{cy-9} {x+4},{cy-17} {x+26},{cy} "
           f"{x+4},{cy+17} {x+4},{cy+9} {x-24},{cy+9}")
    g = [f'<polygon points="{pts}" fill="{color}"/>']
    wd = len(label) * 6.2 + 14
    g.append(rr(gx + 1 - wd / 2, cy - 44, wd, 20, fill="#ffffff", stroke="#e2e8f1", rx=10))
    g.append(txt(gx + 1, cy - 30, label, size=10.5, w=600, fill="#3a4557"))
    return "".join(g)


# -------------------------------------------------------------------- icons ---
def ic_cube(cx, cy):
    b = "#6A4FB3"
    return (f'<path d="M{cx},{cy-12} L{cx+11},{cy-6} L{cx},{cy} L{cx-11},{cy-6} Z" '
            f'fill="#efeafa" stroke="{b}" stroke-width="1.5"/>'
            f'<path d="M{cx-11},{cy-6} L{cx},{cy} L{cx},{cy+12} L{cx-11},{cy+6} Z" '
            f'fill="#e0d7f5" stroke="{b}" stroke-width="1.5"/>'
            f'<path d="M{cx+11},{cy-6} L{cx},{cy} L{cx},{cy+12} L{cx+11},{cy+6} Z" '
            f'fill="#d1c4ec" stroke="{b}" stroke-width="1.5"/>')


def ic_db(cx, cy):
    b = "#2AA79B"
    return (f'<g fill="#dcf2ee" stroke="{b}" stroke-width="1.6">'
            f'<ellipse cx="{cx}" cy="{cy-8}" rx="11" ry="4"/>'
            f'<path d="M{cx-11},{cy-8} L{cx-11},{cy+8} Q{cx},{cy+13} {cx+11},{cy+8} L{cx+11},{cy-8}"/></g>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="11" ry="4" fill="none" stroke="{b}" stroke-width="1.3"/>')


def ic_table(cx, cy):
    b = "#2AA79B"
    g = [f'<rect x="{cx-11}" y="{cy-9}" width="22" height="18" rx="2" fill="#e3f5f2" '
         f'stroke="{b}" stroke-width="1.4"/>']
    g.append(f'<line x1="{cx-11}" y1="{cy-3}" x2="{cx+11}" y2="{cy-3}" stroke="{b}" stroke-width="1.2"/>')
    g.append(f'<line x1="{cx-11}" y1="{cy+3}" x2="{cx+11}" y2="{cy+3}" stroke="{b}" stroke-width="1"/>')
    g.append(f'<line x1="{cx-3}" y1="{cy-9}" x2="{cx-3}" y2="{cy+9}" stroke="{b}" stroke-width="1"/>')
    return "".join(g)


def ic_graph(cx, cy, b="#3f8f3f", node="#7BC67B"):
    return (f'<g stroke="{b}" stroke-width="1.8">'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx+9}" y2="{cy-4}"/>'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx-6}" y2="{cy+9}"/>'
            f'<line x1="{cx+9}" y1="{cy-4}" x2="{cx-6}" y2="{cy+9}"/></g>'
            f'<circle cx="{cx-9}" cy="{cy-8}" r="3.6" fill="{node}"/>'
            f'<circle cx="{cx+9}" cy="{cy-4}" r="3.6" fill="{node}"/>'
            f'<circle cx="{cx-6}" cy="{cy+9}" r="3.6" fill="{node}"/>')


def ic_func(cx, cy, b="#2E7CC4"):
    return (f'<circle cx="{cx}" cy="{cy}" r="10" fill="#e6f1fb" stroke="{b}" stroke-width="1.5"/>'
            f'{txt(cx, cy+5, "\u0192(x)", size=10.5, w=700, fill=b)}')


def ic_bolt(cx, cy):
    return (f'<path d="M{cx+2},{cy-11} L{cx-6},{cy+1} L{cx},{cy+1} L{cx-2},{cy+11} '
            f'L{cx+7},{cy-2} L{cx+1},{cy-2} Z" fill="#E8A23D" stroke="#b8781f" stroke-width="1"/>')


def ic_dash(cx, cy, b="#C9962E"):
    return (f'<rect x="{cx-12}" y="{cy-10}" width="24" height="20" rx="3" fill="#faf1dc" '
            f'stroke="{b}" stroke-width="1.6"/>'
            f'<g stroke="{b}" stroke-width="2" stroke-linecap="round">'
            f'<line x1="{cx-7}" y1="{cy+5}" x2="{cx-7}" y2="{cy+1}"/>'
            f'<line x1="{cx-2}" y1="{cy+5}" x2="{cx-2}" y2="{cy-3}"/>'
            f'<line x1="{cx+3}" y1="{cy+5}" x2="{cx+3}" y2="{cy-6}"/></g>')


def ic_kpi(cx, cy, b="#C9962E"):
    r = lambda dx, dy: (f'<rect x="{cx+dx}" y="{cy+dy}" width="10" height="8" rx="1.6" '
                        f'fill="#faf1dc" stroke="{b}" stroke-width="1.3"/>')
    return r(-12, -9) + r(2, -9) + r(-12, 1) + r(2, 1)


def ic_tree(cx, cy, b="#C9962E"):
    return (f'<g stroke="{b}" stroke-width="1.5" fill="none">'
            f'<path d="M{cx},{cy-3} L{cx},{cy-7}"/>'
            f'<path d="M{cx-8},{cy+2} L{cx-8},{cy-1} L{cx+8},{cy-1} L{cx+8},{cy+2}"/></g>'
            f'<rect x="{cx-5}" y="{cy-11}" width="10" height="6" rx="1.4" fill="#faf1dc" stroke="{b}" stroke-width="1.4"/>'
            f'<rect x="{cx-13}" y="{cy+2}" width="10" height="6" rx="1.4" fill="#faf1dc" stroke="{b}" stroke-width="1.4"/>'
            f'<rect x="{cx+3}" y="{cy+2}" width="10" height="6" rx="1.4" fill="#faf1dc" stroke="{b}" stroke-width="1.4"/>')


def ic_chat(cx, cy, b="#7A4FB0"):
    dots = "".join(f'<circle cx="{cx-5+i*5}" cy="{cy-2}" r="1.4" fill="{b}"/>' for i in range(3))
    return (f'<path d="M{cx-12},{cy-10} h24 a3,3 0 0 1 3,3 v9 a3,3 0 0 1 -3,3 h-14 '
            f'l-5,5 v-5 h-5 a3,3 0 0 1 -3,-3 v-9 a3,3 0 0 1 3,-3 Z" '
            f'fill="#f2ecfa" stroke="{b}" stroke-width="1.6"/>' + dots)


def ic_spark(cx, cy, b="#7A4FB0"):
    return (f'<path d="M{cx},{cy-12} L{cx+3},{cy-3} L{cx+12},{cy} L{cx+3},{cy+3} '
            f'L{cx},{cy+12} L{cx-3},{cy+3} L{cx-12},{cy} L{cx-3},{cy-3} Z" '
            f'fill="#e9dffb" stroke="{b}" stroke-width="1.4" stroke-linejoin="round"/>'
            f'<circle cx="{cx}" cy="{cy}" r="2" fill="{b}"/>')


def ic_doc(cx, cy, b="#7A4FB0"):
    return (f'<path d="M{cx-8},{cy-11} h11 l5,5 v17 h-16 Z" fill="#f4effb" '
            f'stroke="{b}" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<path d="M{cx+3},{cy-11} v5 h5" fill="none" stroke="{b}" stroke-width="1.5"/>'
            f'<g stroke="{b}" stroke-width="1.3" stroke-linecap="round">'
            f'<line x1="{cx-4}" y1="{cy-1}" x2="{cx+5}" y2="{cy-1}"/>'
            f'<line x1="{cx-4}" y1="{cy+3}" x2="{cx+5}" y2="{cy+3}"/>'
            f'<line x1="{cx-4}" y1="{cy+7}" x2="{cx+2}" y2="{cy+7}"/></g>')


def ic_onelake(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="#2E7CC4"/>'
            f'<path d="M{cx-8},{cy+2} q8,-9 16,0" fill="none" stroke="#fff" stroke-width="2.4"/>'
            f'<path d="M{cx-8},{cy+7} q8,-9 16,0" fill="none" stroke="#cfe6fb" stroke-width="2"/>')


# ------------------------------------------------------ composite helpers -----
def stile(x, y, w, h, icon, title, subs=None, accent="#dbe3ee", title_mono=False,
          tsize=13.5, fill="#ffffff"):
    g = [rr(x, y, w, h, fill=fill, stroke=accent, shadow=True, rx=12)]
    g.append(icon(x + 30, y + 32))
    g.append(txt(x + 54, y + 30, title, size=tsize, w=700, anchor="start", mono=title_mono))
    yy = y + 52
    for line in (subs or []):
        s, mono = line if isinstance(line, tuple) else (line, False)
        g.append(txt(x + 54, yy, s, size=11.3, w=400, anchor="start", fill=GRAY, mono=mono))
        yy += 17
    return "".join(g)


def stage_header(x, w, accent, tint, icon, num, title, sub):
    g = [rr(x, 150, w, 60, fill=tint, stroke=accent, sw=1.6, rx=12)]
    g.append(icon(x + 34, 182))
    g.append(txt(x + 58, 176, f"{num}.  {title}", size=15, w=700, anchor="start"))
    g.append(txt(x + 58, 197, sub, size=11.5, w=400, anchor="start", fill=GRAY))
    return "".join(g)


# ------------------------------------------------------------------ assemble --
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">']
S.append('<defs>'
         '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#eef4fb"/><stop offset="1" stop-color="#eef7f4"/></linearGradient>'
         '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
         '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.13"/></filter>'
         '</defs>')
S.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>')

# ---- title -------------------------------------------------------------------
S.append(txt(860, 52, "One Semantic Model in Microsoft Fabric \u2014 Portfolio Schedule Risk",
             size=24, w=700))
S.append(txt(860, 80, "A governed semantic model drives the measures, the dashboard, and the "
             "ad-hoc Copilot answer \u2014 one set of numbers, one source of truth",
             size=13.5, w=400, fill=GRAY))
# model badge
S.append(rr(1398, 96, 266, 34, fill="#ffffff", stroke="#bfe0c8", rx=17, shadow=True))
S.append(ic_cube(1420, 113))
S.append(txt(1438, 118, "Fabric semantic model \u00b7 Direct Lake", size=12, w=700,
             anchor="start", fill="#2f6f3f"))

# ---- stage geometry ----------------------------------------------------------
CW = 370
xs = [58, 474, 890, 1306]
A1, T1 = "#6A4FB3", "#f1ecfa"      # model
A2, T2 = "#2E7CC4", "#e6f1fb"      # measures
A3, T3 = "#C9962E", "#faf3e2"      # dashboard
A4, T4 = "#7A4FB0", "#f1ebf8"      # Q&A / Copilot

# STAGE 1 — Semantic model -----------------------------------------------------
x = xs[0]
S.append(stage_header(x, CW, A1, T1, ic_cube, 1, "Model \u00b7 Semantic Model",
                      "ProjectControlsIQ"))
S.append(stile(x + 8, 226, CW - 16, 96, ic_db, "Direct Lake on gold",
               [("reads curated gold tables in place", False),
                ("no import copy \u00b7 always current", False)], accent="#cdc0e6"))
S.append(stile(x + 8, 334, CW - 16, 122, ic_table, "Star schema \u2014 facts & dims",
               [("dim_project \u00b7 fact_schedule_activity", True),
                ("sap_fi_cost \u00b7 sap_mm_po", True),
                ("fact_engineering_change \u00b7 fact_bid", True)], accent="#cdc0e6",
               tsize=13))
S.append(stile(x + 8, 468, CW - 16, 100, ic_graph, "Relationships modeled once",
               [("SAP \u2194 non-SAP joined on project / WBS", False),
                ("dim_wbs bridges the two worlds", False)], accent="#cdc0e6"))

# STAGE 2 — Measures -----------------------------------------------------------
x = xs[1]
S.append(stage_header(x, CW, A2, T2, lambda a, c: ic_func(a, c, "#2E7CC4"), 2,
                      "Measures \u00b7 DAX logic", "business rules, defined once"))
S.append(stile(x + 8, 226, CW - 16, 122, ic_bolt, "Schedule Risk Score (0\u2013100)",
               [("fused DAX index \u2014 the load-bearing metric", False),
                ("slip \u00b7 float \u00b7 critical-path  (schedule)", False),
                ("+ forecast overrun + late long-lead POs (SAP)", False)],
               accent="#aacdec"))
S.append(stile(x + 8, 360, CW - 16, 96, lambda a, c: ic_func(a, c, "#2E7CC4"),
               "Risk Band + portfolio KPIs",
               [("Risk Band  R / A / G  \u00b7  Projects At Risk", False),
                ("Worst Schedule Risk \u00b7 Avg % Complete", False)], accent="#aacdec"))
S.append(stile(x + 8, 468, CW - 16, 100, lambda a, c: ic_func(a, c, "#2E7CC4"),
               "Component signals",
               [("Forecast Overrun (SAP FI) \u00b7 Late POs (SAP MM)", False),
                ("Schedule Slip \u00b7 Critical Path At Risk", False)], accent="#aacdec"))

# STAGE 3 — Dashboard ----------------------------------------------------------
x = xs[2]
S.append(stage_header(x, CW, A3, T3, lambda a, c: ic_dash(a, c, "#C9962E"), 3,
                      "Visualize \u00b7 Power BI", "dashboard bound to measures"))
S.append(stile(x + 8, 226, CW - 16, 106, lambda a, c: ic_kpi(a, c, "#C9962E"),
               "Executive Portfolio Overview",
               [("project map (lat/lon) \u00b7 KPI cards", False),
                ("%-complete & risk bars \u00b7 12 projects", False)], accent="#e4cf9a"))
S.append(stile(x + 8, 344, CW - 16, 118, lambda a, c: ic_dash(a, c, "#C9962E"),
               "Portfolio Schedule Risk",
               [("Project Falcon is red \u2014 score ~96", False),
                ("SAP late-PO + non-SAP change EC-1207", False),
                ("the two signals, side by side", False)], accent="#e4cf9a"))
S.append(stile(x + 8, 474, CW - 16, 94, lambda a, c: ic_tree(a, c, "#C9962E"),
               "Drill to the drivers",
               [("portfolio \u2192 project \u2192 root cause", False),
                ("every visual reads the same measures", False)], accent="#e4cf9a"))

# STAGE 4 — LLM Q&A ------------------------------------------------------------
x = xs[3]
S.append(stage_header(x, CW, A4, T4, ic_spark, 4, "Ask \u00b7 LLM Q&A",
                      "Copilot \u00b7 natural language"))
S.append(stile(x + 8, 226, CW - 16, 106, ic_chat, "Ad-hoc question",
               [("\u201cWhy is Falcon the top risk this month?\u201d", False),
                ("plain language \u2014 no report author needed", False)], accent="#cdb8e2"))
S.append(stile(x + 8, 344, CW - 16, 118, ic_spark, "Grounded, cited answer",
               [("reads the same model & measures", False),
                ("spans SAP + non-SAP signals", False),
                ("cites the numbers on the dashboard", False)], accent="#cdb8e2"))
S.append(stile(x + 8, 474, CW - 16, 94, ic_doc, "Generate the MPR",
               [("house-style Monthly Progress Report", False),
                ("real numbers \u2014 the artifact Maya needs", False)], accent="#cdb8e2"))

# ---- flow arrows between stages ---------------------------------------------
S.append(flow_arrow(451, 400, "defines measures"))
S.append(flow_arrow(867, 400, "binds to visuals"))
S.append(flow_arrow(1283, 400, "same model, NL query"))

# ---- OneLake foundation ------------------------------------------------------
S.append(rr(58, 640, 1618, 74, fill="#ffffff", opacity=0.9, stroke="#cfe0ee", rx=14, shadow=True))
S.append(ic_onelake(96, 677))
S.append(txt(120, 671, "OneLake \u2014 one copy, one governance", size=15, w=700, anchor="start",
             fill="#2E7CC4"))
S.append(txt(120, 693, "The gold tables behind the model are the same curated data used by "
             "the agents, RTI, and ontology \u2014 one governed semantic layer.",
             size=12, w=400, anchor="start", fill=GRAY))
S.append(rr(1236, 650, 424, 54, fill="#f1ecfa", stroke="#cdc0e6", rx=10))
S.append(ic_cube(1264, 677))
S.append(txt(1286, 672, "ProjectControlsIQ semantic model", size=12, w=700,
             anchor="start", fill="#4a3a78"))
S.append(txt(1286, 690, "dashboards & Copilot resolve to one model", size=10.8, w=400,
             anchor="start", fill=GRAY))

# ---- payoff callout ----------------------------------------------------------
S.append(rr(58, 738, 1618, 46, fill="#fff6ec", stroke="#e7c79a", rx=12))
S.append(ic_bolt(88, 761))
S.append(txt(110, 766, "One model, many answers:", size=13, w=700, anchor="start", fill="#b8781f"))
S.append(txt(338, 766, "the KPI card, the drill-down, and the Copilot answer all compute the "
             "same Schedule Risk Score \u2014 no divergent spreadsheets, one number Maya can defend.",
             size=12.5, w=400, anchor="start", fill="#5b4a2a"))

# ---- presenter note ----------------------------------------------------------
S.append(txt(860, 832, "Demo: Executive Portfolio Overview \u2192 Falcon is red \u2192 drill to "
             "Portfolio Schedule Risk (~96) \u2192 \u201cAsk Copilot: why?\u201d \u2192 cited answer, "
             "then \u201cGenerate the MPR.\u201d", size=12, w=400, italic=True, fill=GRAY))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "semantic_model_scenario.svg")
png_path = os.path.join(here, "semantic_model_scenario.png")
with open(svg_path, "w", encoding="utf-8") as f:
    f.write(svg_text)
print("wrote", svg_path)
try:
    import cairosvg
    cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), write_to=png_path,
                     output_width=W * 2, output_height=H * 2)
    print("wrote", png_path)
except Exception as e:  # noqa
    print("PNG export skipped:", e)
