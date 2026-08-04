#!/usr/bin/env python3
"""Generate the Project Controls IQ ontology diagram (SVG + PNG).

Matches the ontology as implemented. Entities are color-coded by the source
system that backs their data binding:
  green  = Fabric / OneLake
  blue   = Google BigQuery (mirrored database)
  red    = SAP

Relationships are drawn as labeled directed edges.
"""
import os

# ---- palette: key -> (fill, stroke, legend label) ----------------------------
COLORS = {
    "fabric":   ("#C6EFCE", "#2E7D32", "Fabric / OneLake"),
    "s3":       ("#FFEB9C", "#B7860B", "Amazon S3 (Delta shortcut)"),
    "bigquery": ("#BDD7EE", "#1F4E79", "Google BigQuery (mirrored)"),
    "sap":      ("#F4C7C3", "#C0392B", "SAP"),
}
TEXT_DARK = "#1a1a1a"

BOX_W, BOX_H = 208, 72
HW, HH = BOX_W / 2, BOX_H / 2

# ---- nodes: name -> (cx, cy, source) -----------------------------------------
NODES = {
    "Project":                (175, 585, "fabric"),
    "WorkBreakdownStructure": (575, 250, "fabric"),
    "Bids":                   (575, 620, "fabric"),
    "Permits":                (575, 975, "fabric"),
    "WorkOrder":              (980, 150, "bigquery"),
    "PurchaseOrder":          (980, 330, "sap"),
    "EngineeringChange":      (980, 470, "fabric"),
    "Suppliers":              (980, 620, "sap"),
    "PermitInspection":       (980, 975, "fabric"),
    "WorkOrderLabor":         (1385, 70, "bigquery"),
    "WorkOrderMaterial":      (1385, 190, "bigquery"),
    "WorkOrderTask":          (1385, 310, "bigquery"),
}

# ---- edges: (source, target, label) ------------------------------------------
EDGES = [
    ("Project", "WorkBreakdownStructure", "project_has_work_breakdown_structure"),
    ("Project", "Bids", "project_has_bid"),
    ("Project", "Permits", "projects_have_permits"),
    ("WorkBreakdownStructure", "WorkOrder", "wbs_has_workorders"),
    ("WorkBreakdownStructure", "PurchaseOrder", "wps_procured_by_purchase_order"),
    ("WorkBreakdownStructure", "EngineeringChange", "wbs_affected_by_change"),
    ("WorkOrder", "WorkOrderLabor", "workorder_has_labor"),
    ("WorkOrder", "WorkOrderMaterial", "workorder_has_material"),
    ("WorkOrder", "WorkOrderTask", "workorder_has_task"),
    ("Bids", "Suppliers", "bid_has_supplier"),
    ("Permits", "PermitInspection", "permit_has_inspection"),
]

W, H = 1620, 1175


def border_point(cx, cy, tx, ty):
    """Point on the box border of (cx,cy) heading toward (tx,ty)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = HW / abs(dx) if dx else 1e9
    sy = HH / abs(dy) if dy else 1e9
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
for s, t, label in EDGES:
    sx, sy, _ = NODES[s]
    tx, ty, _ = NODES[t]
    p0 = border_point(sx, sy, tx, ty)
    p1 = border_point(tx, ty, sx, sy)
    edge_svg.append(
        f'<path d="M{p0[0]:.1f},{p0[1]:.1f} L{p1[0]:.1f},{p1[1]:.1f}" fill="none" '
        'stroke="#8a8a8a" stroke-width="2" marker-end="url(#arrow)"/>'
    )
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
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
for name, (cx, cy, src) in NODES.items():
    fill, stroke, _ = COLORS[src]
    x, y = cx - HW, cy - HH
    svg.append(
        f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="12" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2.5" filter="url(#shadow)"/>'
    )
    # dynamic font size so long names (e.g. WorkBreakdownStructure) fit
    fs = min(19.0, (BOX_W - 20) / (0.60 * max(len(name), 1)))
    svg.append(
        f'<text x="{cx}" y="{cy + fs*0.35:.1f}" font-size="{fs:.1f}" '
        f'font-weight="700" text-anchor="middle" fill="{TEXT_DARK}">{esc(name)}</text>'
    )

# ---- legend (3 sources) ------------------------------------------------------
lx, ly = 40, H - 168
svg.append(
    f'<rect x="{lx}" y="{ly}" width="366" height="124" rx="10" fill="#fafafa" '
    'stroke="#cccccc" stroke-width="1.5"/>'
)
svg.append(
    f'<text x="{lx + 16}" y="{ly + 28}" font-size="15" font-weight="700" '
    f'fill="{TEXT_DARK}">Source system</text>'
)
for i, key in enumerate(["fabric", "bigquery", "sap"]):
    fill, stroke, desc = COLORS[key]
    yy = ly + 52 + i * 22
    svg.append(
        f'<rect x="{lx + 16}" y="{yy - 13}" width="24" height="15" rx="3" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>'
    )
    svg.append(
        f'<text x="{lx + 50}" y="{yy}" font-size="13.5" fill="#333">{esc(desc)}</text>'
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
