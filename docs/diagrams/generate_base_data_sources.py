#!/usr/bin/env python3
"""Generate the Base Data (source integration) diagram (SVG + PNG).

A simplified, color-coded summary of the data we integrated into OneLake, one
card per source system (colors match solution_overview.png):
  Fabric Native (green) - project controls + permits
  SAP (red)             - suppliers, POs, cost
  BigQuery (blue)       - work-order management
  SQL Server (purple)   - on-prem time clock / labor
Every source is keyed to the same project / WBS / supplier / asset IDs and
lands in one bronze lakehouse via mirroring, shortcuts, and ELT.
"""
import os

W, H = 1720, 726
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


def top_band(x, y, w, h, fill, rx=12):
    return (f'<path d="M{x},{y+rx} Q{x},{y} {x+rx},{y} H{x+w-rx} Q{x+w},{y} {x+w},{y+rx} '
            f'V{y+h} H{x} Z" fill="{fill}"/>')


def onelake_icon(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="#2E7CC4"/>'
            f'<path d="M{cx-8},{cy+2} q8,-9 16,0" fill="none" stroke="#fff" stroke-width="2.4"/>'
            f'<path d="M{cx-8},{cy+7} q8,-9 16,0" fill="none" stroke="#cfe6fb" stroke-width="2"/>')


def bolt(cx, cy):
    return (f'<path d="M{cx+2},{cy-11} L{cx-6},{cy+1} L{cx},{cy+1} L{cx-2},{cy+11} '
            f'L{cx+7},{cy-2} L{cx+1},{cy-2} Z" fill="#E8A23D" stroke="#b8781f" stroke-width="1"/>')


def stream(cx, cy):
    t = "#1f8f84"
    return "".join(
        f'<path d="M{cx-11+o},{cy-6} L{cx-5+o},{cy} L{cx-11+o},{cy+6}" fill="none" '
        f'stroke="{t}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
        for o in (0, 8, 16))


# ------------------------------------------------------------------- card ------
CW, CY, CH = 304, 200, 328


def card(x, color, tint, short, name, method, subject, entities, hero):
    g = [rr(x, CY, CW, CH, fill="#ffffff", stroke=color, sw=1.8, shadow=True, rx=12)]
    # header band
    g.append(top_band(x, CY, CW, 50, color))
    # white badge with source short code
    g.append(rr(x + 14, CY + 12, 46, 26, fill="#ffffff", stroke="#ffffff", rx=7))
    g.append(txt(x + 37, CY + 30, short, size=12.5, w=800, fill=color))
    g.append(txt(x + 70, CY + 31, name, size=14.5, w=700, anchor="start", fill="#ffffff"))
    # ingestion method pill
    g.append(rr(x + 14, CY + 62, CW - 28, 24, fill=tint, stroke=color, sw=1.1, rx=12))
    g.append(txt(x + CW / 2, CY + 78, method, size=11, w=700, fill=color))
    # subject
    g.append(txt(x + 16, CY + 108, subject, size=12.5, w=700, anchor="start", fill=DARK))
    # entity list
    yy = CY + 132
    for e in entities:
        g.append(f'<circle cx="{x+22}" cy="{yy-4}" r="3.2" fill="{color}"/>')
        g.append(txt(x + 32, yy, e, size=12, w=400, anchor="start", fill="#33404f"))
        yy += 24
    # hero tie-in footer
    g.append(rr(x + 12, CY + CH - 52, CW - 24, 40, fill=tint, stroke="none", rx=9))
    g.append(txt(x + 22, CY + CH - 34, "Falcon hero tie-in", size=9.5, w=700,
                 anchor="start", fill=color))
    g.append(txt(x + 22, CY + CH - 19, hero, size=10.8, w=400, anchor="start", fill="#4a5563"))
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
S.append(txt(860, 52, "Base Data \u2014 What We Integrated, and From Where", size=24, w=700))
S.append(txt(860, 80, "Four source systems unified in OneLake \u2014 color-coded by origin, so "
             "you can see which system owns each slice of data before the demos",
             size=13.5, w=400, fill=GRAY))

# ---- source-color legend chip (top-right) -----------------------------------
S.append(rr(1360, 96, 304, 34, fill="#ffffff", stroke="#cfe0ee", rx=17, shadow=True))
S.append(txt(1378, 118, "Color = source system", size=12, w=700, anchor="start", fill=GRAY))
for i, c in enumerate(["#2AA79B", "#C0392B", "#3B7DD8", "#8657C6"]):
    S.append(f'<circle cx="{1548+i*22}" cy="{113}" r="7" fill="{c}"/>')

# ---- cards -------------------------------------------------------------------
xs = [58, 490, 922, 1354]

card_data = [
    dict(x=xs[0], color="#2AA79B", tint="#e3f5f2", short="FN", name="Fabric Native",
         method="Native lakehouse \u00b7 gold model",
         subject="Project controls (core)",
         entities=["Projects & portfolio", "Work Breakdown Structure",
                   "Schedule activities & float", "Engineering changes",
                   "Bids, RFQs & tech evals", "Permits & inspections"],
         hero="Project Falcon (PRJ-001) \u00b7 change EC-1207"),
    dict(x=xs[1], color="#C0392B", tint="#fbe9e7", short="SAP", name="SAP",
         method="ELT pipeline \u2192 landing",
         subject="Suppliers, POs & cost",
         entities=["Suppliers (vendor master)", "Purchase orders (MM)",
                   "Cost & budget (FI)", "Forecast vs. budget", "Earned value",
                   "Long-lead PO status"],
         hero="Late long-lead PO drives Falcon risk"),
    dict(x=xs[2], color="#3B7DD8", tint="#e6f1fb", short="BQ", name="BigQuery",
         method="Mirroring \u2192 shortcut",
         subject="Work-order management",
         entities=["Equipment / assets", "Work orders", "WO tasks",
                   "WO labor", "WO materials (\u2192 supplier)", "WO status history"],
         hero="Emergency WO-900001 on ET-1001"),
    dict(x=xs[3], color="#8657C6", tint="#efe7f9", short="SQL", name="SQL Server",
         method="Mirroring \u2192 shortcut",
         subject="On-prem time clock / labor",
         entities=["Employees", "Crews", "Cost codes", "Timesheets",
                   "Time entries (\u2192 project/WBS)", "Labor charges"],
         hero="Saturday overtime crunch on Falcon"),
]
for c in card_data:
    S.append(card(**c))

# ---- OneLake foundation ------------------------------------------------------
fy = 560
S.append(rr(58, fy, 1606, 76, fill="#ffffff", opacity=0.92, stroke="#cfe0ee", rx=14, shadow=True))
S.append(onelake_icon(96, fy + 38))
S.append(txt(120, fy + 32, "OneLake \u2014 one bronze lakehouse, one governance", size=15, w=700,
             anchor="start", fill="#2E7CC4"))
S.append(txt(120, fy + 55, "Mirroring, shortcuts, and ELT bring every source together with no "
             "second copy \u2014 all keyed to the same project, WBS, supplier & asset IDs.",
             size=12, w=400, anchor="start", fill=GRAY))
# ingestion-pattern legend
S.append(rr(1146, fy + 16, 500, 44, fill="#eef7f4", stroke="#cfe0ee", rx=10))
S.append(txt(1166, fy + 34, "Ingestion patterns", size=10, w=700, anchor="start", fill=GRAY))
S.append(txt(1166, fy + 51, "Mirroring \u00b7 Shortcuts \u00b7 ELT pipeline", size=12, w=600,
             anchor="start", fill="#33404f"))

# ---- RTI live-source callout -------------------------------------------------
cy2 = 656
S.append(rr(58, cy2, 1606, 48, fill="#eef7f4", stroke="#bfe0c8", rx=12))
S.append(stream(90, cy2 + 24))
S.append(txt(118, cy2 + 22, "Plus a live source:", size=12.5, w=700, anchor="start",
             fill="#1f8f84"))
S.append(txt(262, cy2 + 22, "equipment commissioning telemetry (IIoT) streams in real time via "
             "Eventstream \u2192 Eventhouse/KQL \u2014 the ET-1001 transformer feed behind the RTI demo.",
             size=12, w=400, anchor="start", fill="#3a5148"))
S.append(txt(118, cy2 + 39, "See the Real-Time Intelligence diagram for that pipeline.",
             size=10.8, w=400, italic=True, anchor="start", fill=GRAY))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "base_data_sources.svg")
png_path = os.path.join(here, "base_data_sources.png")
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
