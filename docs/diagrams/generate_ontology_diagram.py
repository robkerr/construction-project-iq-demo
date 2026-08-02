#!/usr/bin/env python3
"""Generate the Project Controls IQ ontology diagram (SVG + PNG).

Entities are color-coded by the source system that backs their data binding:
  green  = OneLake / Fabric managed tables
  blue   = Google BigQuery (mirrored database, shortcut)
  yellow = Amazon S3 (Delta shortcut)

Relationships are drawn as labeled directed edges. See
design/ontology_design.md for the underlying entity/relationship spec.
"""
import math
import os

# ---- palette -----------------------------------------------------------------
COLORS = {
    "onelake":  ("#C6EFCE", "#2E7D32", "OneLake (Fabric tables)"),
    "bigquery": ("#BDD7EE", "#1F4E79", "Google BigQuery (mirrored)"),
    "s3":       ("#FFEB9C", "#B7860B", "Amazon S3 (Delta shortcut)"),
}
TEXT_DARK = "#1a1a1a"

# ---- nodes: name -> (cx, cy, source, subtitle) -------------------------------
BOX_W, BOX_H = 202, 72
HW, HH = BOX_W / 2, BOX_H / 2

NODES = {
    "Project":            (160, 500, "onelake",  "gold.project_schedule_risk"),
    "WorkPackage":        (470, 330, "onelake",  "silver.dim_wbs"),
    "EngineeringChange":  (470, 130, "onelake",  "silver.fact_engineering_change"),
    "Equipment":          (470, 690, "bigquery", "BigQuery asset + RTI stream"),
    "WorkOrder":          (160, 850, "bigquery", "BigQuery: work_order"),
    "PurchaseOrder":      (800, 250, "onelake",  "silver.sap_mm_po"),
    "RFQ":                (800, 520, "onelake",  "silver.dim_rfq"),
    "Permit":             (800, 850, "s3",       "S3 shortcut: permit"),
    "Supplier":           (1150, 250, "onelake", "silver.sap_supplier"),
    "Bid":                (1410, 440, "onelake", "gold.bid_evaluation"),
}

# ---- edges: (source, target, label, curve_ctrl or None) ----------------------
EDGES = [
    ("Project", "WorkPackage", "contains", None),
    ("Project", "Equipment", "hasAsset", None),
    ("Project", "RFQ", "issues", None),
    ("Project", "Permit", "hasPermit", (300, 940)),
    ("WorkPackage", "EngineeringChange", "affectedByChange", None),
    ("WorkPackage", "PurchaseOrder", "procuredVia", None),
    ("WorkPackage", "Equipment", "scopes", None),
    ("Supplier", "PurchaseOrder", "fulfills", None),
    ("Supplier", "Bid", "submits", None),
    ("RFQ", "Equipment", "forEquipment", None),
    ("RFQ", "Bid", "receivesBid", None),
    ("Equipment", "WorkOrder", "hasWorkOrder", None),
]

W, H = 1580, 1010


def border_point(cx, cy, tx, ty):
    """Point on the box border of (cx,cy) heading toward (tx,ty)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = HW / abs(dx) if dx else math.inf
    sy = HH / abs(dy) if dy else math.inf
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


svg = []
svg.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">'
)
svg.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>')
svg.append(
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#5a5a5a"/></marker>'
    '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
    '<feDropShadow dx="0" dy="2" stdDeviation="2.2" flood-color="#000" '
    'flood-opacity="0.18"/></filter></defs>'
)

# ---- title -------------------------------------------------------------------
svg.append(
    f'<text x="40" y="52" font-size="30" font-weight="700" fill="{TEXT_DARK}">'
    'Project Controls IQ — Fabric IQ Ontology</text>'
)
svg.append(
    f'<text x="41" y="82" font-size="16" fill="#555">'
    'Entities colored by source system &#8226; relationships labeled with their titles</text>'
)

# ---- edges (draw before nodes so nodes sit on top) ---------------------------
edge_svg, label_svg = [], []
for s, t, label, ctrl in EDGES:
    sx, sy, *_ = NODES[s]
    tx, ty, *_ = NODES[t]
    if ctrl is None:
        p0 = border_point(sx, sy, tx, ty)
        p1 = border_point(tx, ty, sx, sy)
        path = f'M{p0[0]:.1f},{p0[1]:.1f} L{p1[0]:.1f},{p1[1]:.1f}'
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    else:
        cxp, cyp = ctrl
        p0 = border_point(sx, sy, cxp, cyp)
        p1 = border_point(tx, ty, cxp, cyp)
        path = f'M{p0[0]:.1f},{p0[1]:.1f} Q{cxp},{cyp} {p1[0]:.1f},{p1[1]:.1f}'
        mx = 0.25 * p0[0] + 0.5 * cxp + 0.25 * p1[0]
        my = 0.25 * p0[1] + 0.5 * cyp + 0.25 * p1[1]
    edge_svg.append(
        f'<path d="{path}" fill="none" stroke="#8a8a8a" stroke-width="2" '
        'marker-end="url(#arrow)"/>'
    )
    # label with white pill background
    fw = len(label) * 7.4 + 14
    label_svg.append(
        f'<g>'
        f'<rect x="{mx - fw/2:.1f}" y="{my - 12:.1f}" width="{fw:.1f}" height="22" '
        f'rx="8" fill="#ffffff" stroke="#d0d0d0" stroke-width="1"/>'
        f'<text x="{mx:.1f}" y="{my + 3:.1f}" font-size="13.5" font-style="italic" '
        f'text-anchor="middle" fill="#444">{esc(label)}</text></g>'
    )
svg.extend(edge_svg)
svg.extend(label_svg)

# ---- nodes -------------------------------------------------------------------
for name, (cx, cy, src, sub) in NODES.items():
    fill, stroke, _ = COLORS[src]
    x, y = cx - HW, cy - HH
    svg.append(
        f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="12" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2.5" filter="url(#shadow)"/>'
    )
    svg.append(
        f'<text x="{cx}" y="{cy - 4}" font-size="18" font-weight="700" '
        f'text-anchor="middle" fill="{TEXT_DARK}">{esc(name)}</text>'
    )
    svg.append(
        f'<text x="{cx}" y="{cy + 17}" font-size="11" text-anchor="middle" '
        f'fill="#555" font-family="Consolas, monospace">{esc(sub)}</text>'
    )

# ---- legend ------------------------------------------------------------------
lx, ly = 40, H - 118
svg.append(
    f'<rect x="{lx}" y="{ly}" width="360" height="98" rx="10" fill="#fafafa" '
    'stroke="#cccccc" stroke-width="1.5"/>'
)
svg.append(
    f'<text x="{lx + 16}" y="{ly + 26}" font-size="15" font-weight="700" '
    f'fill="{TEXT_DARK}">Source system</text>'
)
for i, key in enumerate(["onelake", "bigquery", "s3"]):
    fill, stroke, desc = COLORS[key]
    yy = ly + 44 + i * 18
    svg.append(
        f'<rect x="{lx + 16}" y="{yy - 12}" width="22" height="14" rx="3" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>'
    )
    svg.append(
        f'<text x="{lx + 46}" y="{yy}" font-size="13.5" fill="#333">{esc(desc)}</text>'
    )

svg.append("</svg>")
svg_text = "\n".join(svg)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "ontology_diagram.svg")
png_path = os.path.join(here, "ontology_diagram.png")
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
