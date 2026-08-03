#!/usr/bin/env python3
"""Generate the 'Four EPC Agents' intro-slide diagram (SVG + PNG).

An at-a-glance overview slide shown before we open each Foundry agent. One card
per agent: what it does, its persona, how it grounds, and the ontology entities
it consumes (color-coded by source system to tie back to the ontology diagram).
"""
import os

W, H = 1720, 1080
DARK = "#1f2430"
GRAY = "#5b6472"

# entity source palette (matches the ontology diagram)
SRC = {
    "fabric": ("#C6EFCE", "#2E7D32"),
    "sap":    ("#F4C7C3", "#C0392B"),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rr(x, y, w, h, fill="#ffffff", stroke="#c9d2de", sw=1.6, rx=12,
       dash=None, shadow=False, opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    f = ' filter="url(#sh)"' if shadow else ''
    o = f' fill-opacity="{opacity}"' if opacity is not None else ''
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'
            f' stroke="{stroke}" stroke-width="{sw}"{d}{f}{o}/>')


def txt(x, y, s, size=14, w=400, anchor="middle", fill=DARK, italic=False):
    it = ' font-style="italic"' if italic else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" '
            f'text-anchor="{anchor}" fill="{fill}" '
            f'font-family="Segoe UI, Arial, sans-serif"{it}>{esc(s)}</text>')


def entity_chip(x, y, label, src):
    """A small rounded, source-colored entity tag. Returns (svg, width)."""
    fill, stroke = SRC[src]
    w = len(label) * 7.2 + 22
    g = (rr(x, y, w, 26, fill=fill, stroke=stroke, sw=1.5, rx=13) +
         txt(x + w / 2, y + 17.5, label, size=12.5, w=600, fill="#243024"))
    return g, w


# ------------------------------------------------------------------ content ---
AGENTS = [
    dict(
        n="1", accent="#2A6FB0", title="Technical Bid Evaluation",
        aid="epc-technical-bid-evaluation", persona="Priya \u00b7 Procurement",
        hero="Hero: RFQ-0001 \u00b7 tag ET-1001 (230 kV transformer)",
        does=["Scores each bidder's technical compliance against the",
              "equipment datasheet, flags mandatory-spec exceptions,",
              "and returns the technically qualified shortlist."],
        consumes=[("Bids", "fabric"), ("Suppliers", "sap")],
    ),
    dict(
        n="2", accent="#6A4FB3", title="Commercial Bid Evaluation",
        aid="epc-commercial-bid-evaluation", persona="Priya \u00b7 Procurement",
        hero="Hero: RFQ-0001 \u00b7 downstream of the TBE",
        does=["Normalizes each qualified bidder's quote to an evaluated",
              "price (spares, freight, delay, financing, warranty) and",
              "recommends the lowest-evaluated award."],
        consumes=[("Bids", "fabric"), ("Suppliers", "sap")],
    ),
    dict(
        n="3", accent="#2AA79B", title="Monthly Progress Report",
        aid="epc-monthly-progress-report", persona="Maya \u00b7 Project Controls",
        hero="Hero: PRJ-001 Project Falcon",
        does=["Fuses SAP cost / procurement and non-SAP schedule / change",
              "facts into a leadership-ready status \u2014 with a schedule-risk",
              "score, risk band, and the cross-system finding."],
        consumes=[("Project", "fabric"), ("WBS", "fabric"),
                  ("PurchaseOrder", "sap"), ("EngineeringChange", "fabric"),
                  ("Suppliers", "sap")],
    ),
    dict(
        n="4", accent="#E8912A", title="Change Notice",
        aid="epc-change-notice", persona="Change Mgr \u00b7 Project Controls",
        hero="Hero: EC-1207 + late long-lead PO-00510 on WBS-00001",
        does=["Drafts a formal change notice linking an approved engineering",
              "change and a late long-lead PO on the same WBS \u2014 with the",
              "schedule and cost impact quantified."],
        consumes=[("EngineeringChange", "fabric"), ("PurchaseOrder", "sap"),
                  ("Project", "fabric"), ("WBS", "fabric")],
    ),
]

# ------------------------------------------------------------------ assemble --
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">']
S.append('<defs>'
         '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#eef4fb"/><stop offset="1" stop-color="#f6eff3"/></linearGradient>'
         '<linearGradient id="fdy" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#9a6ff0"/><stop offset="1" stop-color="#6a3fd0"/></linearGradient>'
         '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
         '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.13"/></filter>'
         '</defs>')
S.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>')

# ---- title -------------------------------------------------------------------
S.append(txt(60, 62, "The Four EPC Agents \u2014 What They Do & What They Ground On",
             size=30, w=700, anchor="start"))
S.append(txt(61, 92,
             "Grounded Azure AI Foundry agents for the Contoso E&C demo \u2014 an intro before we open each one",
             size=15, w=400, anchor="start", fill=GRAY))

# ---- Foundry hex badge (top-right) ------------------------------------------
import math
hx, hy = W - 70, 60
pts = " ".join(f"{hx + 15*math.cos(math.radians(a)):.1f},{hy + 15*math.sin(math.radians(a)):.1f}"
               for a in range(0, 360, 60))
S.append(f'<polygon points="{pts}" fill="url(#fdy)" stroke="#5b3fa0" stroke-width="1.5"/>')
S.append(txt(W - 95, 65, "Microsoft Foundry", size=13, w=700, anchor="end", fill="#3a4557"))

# ---- agent cards (2x2 grid) --------------------------------------------------
MX, TOP = 60, 128
GAP_X, GAP_Y = 36, 30
CARD_W = (W - 2 * MX - GAP_X) / 2          # 794
CARD_H = 358
positions = [(MX, TOP), (MX + CARD_W + GAP_X, TOP),
             (MX, TOP + CARD_H + GAP_Y), (MX + CARD_W + GAP_X, TOP + CARD_H + GAP_Y)]

for ag, (cx, cy) in zip(AGENTS, positions):
    accent = ag["accent"]
    S.append(rr(cx, cy, CARD_W, CARD_H, shadow=True, stroke="#c4cdda", sw=1.6, rx=18))
    # accent header strip
    S.append(f'<path d="M{cx+18},{cy} h{CARD_W-36} a18,18 0 0 1 18,18 v34 h-{CARD_W} v-34 '
             f'a18,18 0 0 1 18,-18 z" fill="{accent}" fill-opacity="0.12"/>')
    # number medallion
    S.append(f'<circle cx="{cx+42}" cy="{cy+34}" r="20" fill="{accent}"/>')
    S.append(txt(cx + 42, cy + 41, ag["n"], size=21, w=700, fill="#ffffff"))
    # title + agent id
    S.append(txt(cx + 76, cy + 30, ag["title"], size=20, w=700, anchor="start"))
    S.append(txt(cx + 76, cy + 49, ag["aid"], size=12.5, w=400, anchor="start", fill=accent))
    # persona chip (right of header)
    pw = len(ag["persona"]) * 7.0 + 26
    S.append(rr(cx + CARD_W - pw - 18, cy + 20, pw, 28, fill="#ffffff",
                stroke=accent, sw=1.5, rx=14))
    S.append(txt(cx + CARD_W - pw / 2 - 18, cy + 39, ag["persona"], size=12.5, w=600, fill=accent))

    # "What it does"
    yy = cy + 82
    S.append(txt(cx + 28, yy, "WHAT IT DOES", size=11.5, w=700, anchor="start", fill=GRAY))
    for i, line in enumerate(ag["does"]):
        S.append(txt(cx + 28, yy + 22 + i * 21, line, size=14.5, w=400, anchor="start", fill=DARK))
    # hero note
    S.append(txt(cx + 28, yy + 22 + len(ag["does"]) * 21 + 6, ag["hero"],
                 size=12.5, w=400, anchor="start", fill=GRAY, italic=True))

    # "How it works"
    hy2 = cy + 232
    S.append(txt(cx + 28, hy2, "HOW IT WORKS", size=11.5, w=700, anchor="start", fill=GRAY))
    S.append(txt(cx + 28, hy2 + 21, "gpt-4.1 prompt agent \u00b7 grounded on the EPCOntology via the",
                 size=13.5, w=400, anchor="start", fill=DARK))
    S.append(txt(cx + 28, hy2 + 40, "native Fabric IQ tool (Entra passthrough \u2014 no secrets).",
                 size=13.5, w=400, anchor="start", fill=DARK))

    # "Consumes" entity chips
    cyy = cy + 300
    S.append(txt(cx + 28, cyy, "CONSUMES", size=11.5, w=700, anchor="start", fill=GRAY))
    ex = cx + 28
    ey = cyy + 12
    for label, src in ag["consumes"]:
        chip_svg, w = entity_chip(ex, ey, label, src)
        if ex + w > cx + CARD_W - 24:      # wrap to next row if needed
            ex = cx + 28
            ey += 32
            chip_svg, w = entity_chip(ex, ey, label, src)
        S.append(chip_svg)
        ex += w + 8

# ---- footer band -------------------------------------------------------------
fy = TOP + 2 * CARD_H + GAP_Y + 22
S.append(rr(MX, fy, W - 2 * MX, 74, fill="#ffffff", opacity=0.9, stroke="#e2e8f1", rx=14))
S.append(txt(MX + 26, fy + 30,
             "Common architecture:  all four are versioned prompt agents in the Foundry project "
             "\u201cfbcaidemo-dev-project\u201d (prefix epc-),",
             size=14, w=600, anchor="start", fill="#3a4557"))
S.append(txt(MX + 26, fy + 52,
             "grounded on one shared Fabric IQ ontology and callable from a custom app "
             "(Entra service principal) or a Copilot session via the Responses API.",
             size=14, w=400, anchor="start", fill="#3a4557"))
# source legend (right side of footer)
lx = W - MX - 300
S.append(rr(lx, fy + 18, 24, 15, fill=SRC["fabric"][0], stroke=SRC["fabric"][1], sw=1.6, rx=3))
S.append(txt(lx + 32, fy + 30, "Fabric / OneLake", size=12, w=400, anchor="start", fill="#333"))
S.append(rr(lx, fy + 40, 24, 15, fill=SRC["sap"][0], stroke=SRC["sap"][1], sw=1.6, rx=3))
S.append(txt(lx + 32, fy + 52, "SAP", size=12, w=400, anchor="start", fill="#333"))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "four_agents_overview.svg")
png_path = os.path.join(here, "four_agents_overview.png")
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
