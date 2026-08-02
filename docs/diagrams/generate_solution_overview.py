#!/usr/bin/env python3
"""Generate the Project Controls IQ demo solution overview diagram (SVG + PNG).

Three sections — Microsoft Fabric, Microsoft 365 Copilot, Microsoft Foundry —
populated with the specific assets built for this demo.
"""
import os

W, H = 1600, 884
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


def txt(x, y, s, size=14, w=400, anchor="middle", fill=DARK, italic=False,
        mono=False):
    fam = 'Consolas, monospace' if mono else 'Segoe UI, Arial, sans-serif'
    it = ' font-style="italic"' if italic else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" '
            f'text-anchor="{anchor}" fill="{fill}" font-family="{fam}"{it}>{s}</text>')


def lines(cx, cy, rows, size=13, w=600, gap=16, fill=DARK):
    out = []
    y = cy - (len(rows) - 1) * gap / 2 + size * 0.35
    for r in rows:
        out.append(txt(cx, y, r, size=size, w=w, fill=fill))
        y += gap
    return "".join(out)


def arrow(x1, y1, x2, y2, double=False, color="#5a6472", sw=2.2):
    ms = ' marker-start="url(#astart)"' if double else ''
    return (f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" marker-end="url(#aend)"{ms}/>')


# -------------------------------------------------------------------- icons ---
def ic_chart(cx, cy):
    b = "#E8A23D"
    return (f'<g stroke="{b}" stroke-width="3" stroke-linecap="round">'
            f'<line x1="{cx-11}" y1="{cy+9}" x2="{cx-11}" y2="{cy+1}"/>'
            f'<line x1="{cx-1}" y1="{cy+9}" x2="{cx-1}" y2="{cy-6}"/>'
            f'<line x1="{cx+9}" y1="{cy+9}" x2="{cx+9}" y2="{cy-10}"/></g>'
            f'<line x1="{cx-16}" y1="{cy+11}" x2="{cx+14}" y2="{cy+11}" '
            f'stroke="#9aa4b2" stroke-width="2"/>')


def _hex(cx, cy, r, fill, stroke):
    import math
    pts = " ".join(f"{cx + r*math.cos(math.radians(a)):.1f},"
                   f"{cy + r*math.sin(math.radians(a)):.1f}"
                   for a in range(0, 360, 60))
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'


def ic_hex(cx, cy):  # data agent
    return (_hex(cx, cy-7, 8, "#7BC67B", "#3f8f3f") +
            _hex(cx-8, cy+6, 8, "#54ad54", "#3f8f3f") +
            _hex(cx+8, cy+6, 8, "#9ad39a", "#3f8f3f"))


def ic_house(cx, cy):
    b = "#2F6FB0"
    return (f'<path d="M{cx-12},{cy+2} L{cx},{cy-11} L{cx+12},{cy+2} Z" '
            f'fill="#bcd7ef" stroke="{b}" stroke-width="1.8"/>'
            f'<rect x="{cx-9}" y="{cy+2}" width="18" height="10" fill="#e8f1fb" '
            f'stroke="{b}" stroke-width="1.8"/>')


def ic_graph(cx, cy):  # ontology
    g = "#3f8f3f"
    return (f'<g stroke="{g}" stroke-width="1.8">'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx+9}" y2="{cy-4}"/>'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx-6}" y2="{cy+9}"/>'
            f'<line x1="{cx+9}" y1="{cy-4}" x2="{cx-6}" y2="{cy+9}"/></g>'
            f'<circle cx="{cx-9}" cy="{cy-8}" r="4" fill="#7BC67B"/>'
            f'<circle cx="{cx+9}" cy="{cy-4}" r="4" fill="#7BC67B"/>'
            f'<circle cx="{cx-6}" cy="{cy+9}" r="4" fill="#7BC67B"/>')


def ic_cube(cx, cy):  # semantic model
    p = "#6A4FB3"
    return (f'<g fill="#d7ccf0" stroke="{p}" stroke-width="1.6">'
            f'<polygon points="{cx},{cy-11} {cx+11},{cy-5} {cx},{cy+1} {cx-11},{cy-5}"/>'
            f'<polygon points="{cx-11},{cy-5} {cx},{cy+1} {cx},{cy+12} {cx-11},{cy+6}" fill="#c3b4e6"/>'
            f'<polygon points="{cx+11},{cy-5} {cx},{cy+1} {cx},{cy+12} {cx+11},{cy+6}" fill="#b3a1df"/></g>')


def ic_robot(cx, cy):
    b = "#2E7CC4"
    return (f'<rect x="{cx-11}" y="{cy-8}" width="22" height="17" rx="5" '
            f'fill="#d6ecfb" stroke="{b}" stroke-width="1.8"/>'
            f'<circle cx="{cx-4}" cy="{cy}" r="2.4" fill="{b}"/>'
            f'<circle cx="{cx+4}" cy="{cy}" r="2.4" fill="{b}"/>'
            f'<line x1="{cx}" y1="{cy-8}" x2="{cx}" y2="{cy-13}" stroke="{b}" stroke-width="1.8"/>'
            f'<circle cx="{cx}" cy="{cy-14}" r="2" fill="{b}"/>')


def ic_flow(cx, cy):
    t = "#2AA6A6"
    return (f'<g stroke="{t}" stroke-width="1.8"><line x1="{cx-8}" y1="{cy-8}" x2="{cx+6}" y2="{cy}"/>'
            f'<line x1="{cx-8}" y1="{cy+8}" x2="{cx+6}" y2="{cy}"/></g>'
            f'<circle cx="{cx-9}" cy="{cy-8}" r="3.5" fill="{t}"/>'
            f'<circle cx="{cx-9}" cy="{cy+8}" r="3.5" fill="{t}"/>'
            f'<circle cx="{cx+8}" cy="{cy}" r="4" fill="{t}"/>')


def ic_people(cx, cy):
    b = "#2E7CC4"
    return (f'<circle cx="{cx-6}" cy="{cy-4}" r="4" fill="{b}"/>'
            f'<circle cx="{cx+6}" cy="{cy-4}" r="4" fill="#7bb6e6"/>'
            f'<path d="M{cx-13},{cy+9} q6,-9 13,0" fill="none" stroke="{b}" stroke-width="2.4"/>'
            f'<path d="M{cx-1},{cy+9} q6,-9 13,0" fill="none" stroke="#7bb6e6" stroke-width="2.4"/>')


def ic_cal(cx, cy):
    b = "#C7562E"
    return (f'<rect x="{cx-11}" y="{cy-9}" width="22" height="19" rx="3" fill="#fbe6dd" '
            f'stroke="{b}" stroke-width="1.8"/>'
            f'<line x1="{cx-11}" y1="{cy-3}" x2="{cx+11}" y2="{cy-3}" stroke="{b}" stroke-width="1.8"/>'
            f'<line x1="{cx-5}" y1="{cy-13}" x2="{cx-5}" y2="{cy-7}" stroke="{b}" stroke-width="2"/>'
            f'<line x1="{cx+5}" y1="{cy-13}" x2="{cx+5}" y2="{cy-7}" stroke="{b}" stroke-width="2"/>')


def ic_mail(cx, cy):
    b = "#2E7CC4"
    return (f'<rect x="{cx-12}" y="{cy-8}" width="24" height="17" rx="3" fill="#dcefff" '
            f'stroke="{b}" stroke-width="1.8"/>'
            f'<path d="M{cx-12},{cy-7} L{cx},{cy+2} L{cx+12},{cy-7}" fill="none" '
            f'stroke="{b}" stroke-width="1.8"/>')


def ic_word(cx, cy):
    b = "#2B5797"
    return (f'<rect x="{cx-9}" y="{cy-11}" width="18" height="22" rx="2" fill="#e5edf8" '
            f'stroke="{b}" stroke-width="1.6"/>'
            f'{txt(cx, cy+5, "W", size=13, w=800, fill=b)}')


def ic_search(cx, cy):
    b = "#2E7CC4"
    return (f'<circle cx="{cx-2}" cy="{cy-3}" r="7" fill="#dcefff" stroke="{b}" stroke-width="2"/>'
            f'<line x1="{cx+4}" y1="{cy+3}" x2="{cx+11}" y2="{cy+10}" stroke="{b}" '
            f'stroke-width="2.6" stroke-linecap="round"/>')


def ic_openai(cx, cy):
    import math
    g = "#3a7d5b"
    petals = "".join(
        f'<ellipse cx="{cx+7*math.cos(math.radians(a)):.1f}" '
        f'cy="{cy+7*math.sin(math.radians(a)):.1f}" rx="5" ry="2.6" '
        f'transform="rotate({a} {cx+7*math.cos(math.radians(a)):.1f} '
        f'{cy+7*math.sin(math.radians(a)):.1f})" fill="#bfe3cf" stroke="{g}" '
        f'stroke-width="1"/>' for a in range(0, 360, 60))
    return petals + f'<circle cx="{cx}" cy="{cy}" r="3" fill="{g}"/>'


def ic_gear(cx, cy):
    import math
    b = "#2A6FB0"
    teeth = "".join(
        f'<rect x="{cx-2}" y="{cy-14}" width="4" height="6" fill="{b}" '
        f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 45))
    return (teeth + f'<circle cx="{cx}" cy="{cy}" r="8" fill="#cfe3f5" stroke="{b}" '
            f'stroke-width="2"/><circle cx="{cx}" cy="{cy}" r="3" fill="{b}"/>')


def ic_globe(cx, cy):
    b = "#2A6FB0"
    return (f'<circle cx="{cx}" cy="{cy}" r="11" fill="#d6ecfb" stroke="{b}" stroke-width="1.8"/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="5" ry="11" fill="none" stroke="{b}" stroke-width="1.4"/>'
            f'<line x1="{cx-11}" y1="{cy}" x2="{cx+11}" y2="{cy}" stroke="{b}" stroke-width="1.4"/>')


def ic_doc(cx, cy, accent="#5b6472"):
    return (f'<rect x="{cx-10}" y="{cy-12}" width="20" height="24" rx="2" fill="#f2f5f9" '
            f'stroke="{accent}" stroke-width="1.6"/>'
            f'<g stroke="{accent}" stroke-width="1.5">'
            f'<line x1="{cx-6}" y1="{cy-5}" x2="{cx+6}" y2="{cy-5}"/>'
            f'<line x1="{cx-6}" y1="{cy}" x2="{cx+6}" y2="{cy}"/>'
            f'<line x1="{cx-6}" y1="{cy+5}" x2="{cx+2}" y2="{cy+5}"/></g>')


def ic_alarm(cx, cy):
    r = "#C0392B"
    return (f'<path d="M{cx-10},{cy+6} Q{cx-10},{cy-10} {cx},{cy-10} '
            f'Q{cx+10},{cy-10} {cx+10},{cy+6} Z" fill="#f7d7d3" stroke="{r}" stroke-width="1.8"/>'
            f'<line x1="{cx-12}" y1="{cy+6}" x2="{cx+12}" y2="{cy+6}" stroke="{r}" stroke-width="2"/>'
            f'<circle cx="{cx}" cy="{cy+10}" r="2.4" fill="{r}"/>')


def ic_storage(cx, cy):
    b = "#7a8797"
    return (f'<g fill="#e7ecf2" stroke="{b}" stroke-width="1.5">'
            f'<ellipse cx="{cx}" cy="{cy-7}" rx="12" ry="4"/>'
            f'<path d="M{cx-12},{cy-7} L{cx-12},{cy+7} Q{cx},{cy+12} {cx+12},{cy+7} L{cx+12},{cy-7}"/></g>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="12" ry="4" fill="none" stroke="{b}" stroke-width="1.3"/>')


def ic_onelake(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="#2E7CC4"/>'
            f'<path d="M{cx-8},{cy+2} q8,-9 16,0" fill="none" stroke="#fff" stroke-width="2.4"/>'
            f'<path d="M{cx-8},{cy+7} q8,-9 16,0" fill="none" stroke="#cfe6fb" stroke-width="2"/>')


def logo_fabric(cx, cy):
    return (f'<polygon points="{cx-9},{cy} {cx-3},{cy-8} {cx+2},{cy} {cx-3},{cy+8}" fill="#2AA79B"/>'
            f'<polygon points="{cx-1},{cy-2} {cx+5},{cy-10} {cx+10},{cy-2} {cx+5},{cy+6}" fill="#57C4B6"/>')


def logo_copilot(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="url(#cop)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="5" fill="#fff" fill-opacity="0.85"/>')


def logo_foundry(cx, cy):
    return (_hex(cx, cy, 12, "url(#fdy)", "#5b3fa0"))


def badge(cx, cy, fill, stroke, label, tcolor="#fff", sz=12):
    return (f'<rect x="{cx-16}" y="{cy-13}" width="32" height="26" rx="6" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.6"/>'
            f'{txt(cx, cy+4, label, size=sz, w=800, fill=tcolor)}')


# ------------------------------------------------------------------ assemble --
S = []
S.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">')
S.append('<defs>'
         '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#eaf3fb"/><stop offset="1" stop-color="#f7edf1"/></linearGradient>'
         '<linearGradient id="cop" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#3ab0e6"/><stop offset="0.5" stop-color="#8a63d2"/>'
         '<stop offset="1" stop-color="#e0568f"/></linearGradient>'
         '<linearGradient id="fdy" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#9a6ff0"/><stop offset="1" stop-color="#6a3fd0"/></linearGradient>'
         '<marker id="aend" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7.5" '
         'markerHeight="7.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#5a6472"/></marker>'
         '<marker id="astart" viewBox="0 0 10 10" refX="1.5" refY="5" markerWidth="7.5" '
         'markerHeight="7.5" orient="auto-start-reverse"><path d="M10,0 L0,5 L10,10 z" fill="#5a6472"/></marker>'
         '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
         '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.14"/></filter>'
         '</defs>')
S.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>')

# ---- dashed section regions --------------------------------------------------
S.append(rr(40, 100, 500, 384, fill="none", stroke="#9aa6b6", sw=1.6, rx=16, dash="7 6"))
S.append(rr(566, 100, 474, 410, fill="none", stroke="#9aa6b6", sw=1.6, rx=16, dash="7 6"))
S.append(rr(1066, 100, 500, 410, fill="none", stroke="#9aa6b6", sw=1.6, rx=16, dash="7 6"))

# ---- header pills ------------------------------------------------------------
def header(x, l1, l2, logo):
    g = [rr(x, 40, 210, 56, shadow=True, rx=12, stroke="#dbe2ec")]
    g.append(logo(x + 30, 68))
    g.append(txt(x + 54, 62, l1, size=13, w=400, anchor="start", fill=GRAY))
    g.append(txt(x + 54, 82, l2, size=18, w=700, anchor="start"))
    return "".join(g)

S.append(header(60, "Microsoft", "Fabric", logo_fabric))
S.append(header(596, "Microsoft 365", "Copilot", logo_copilot))
S.append(header(1110, "Microsoft", "Foundry", logo_foundry))

# ---- generic tile ------------------------------------------------------------
def tile(x, y, w, h, rows, icon, rx=12, stroke="#c9d2de", size=12.5):
    cx = x + w / 2
    g = [rr(x, y, w, h, shadow=True, rx=rx, stroke=stroke)]
    g.append(icon(cx, y + 30))
    g.append(lines(cx, y + h - (len(rows) * 8) - 4, rows, size=size, w=600, gap=15))
    return "".join(g)

# ================================ FABRIC ======================================
S.append(tile(78, 150, 150, 118, ["Project Controls", "Dashboards"], ic_chart))
S.append(tile(300, 150, 150, 118, ["Fabric Data", "Agent"], ic_hex))

# semantic-layer container
S.append(rr(60, 300, 456, 168, fill="#ffffff", stroke="#d6deea", opacity=0.55, rx=14))
S.append(tile(78, 320, 132, 130, ["Fabric", "Lakehouse"], ic_house))
S.append(tile(248, 314, 250, 68, ["Semantic Model", "(ProjectControlsIQ)"], ic_cube))
S.append(tile(248, 392, 250, 62, ["Fabric IQ  (Ontology)"], ic_graph))
# internal arrows
S.append(arrow(210, 360, 246, 347))
S.append(arrow(210, 408, 246, 421))
# up to serving tiles
S.append(arrow(330, 316, 200, 270))
S.append(arrow(360, 390, 400, 270))

# data sources + OneLake (below dashed region)
S.append(arrow(240, 484, 240, 508, double=True))
S.append(rr(44, 508, 492, 150, fill="#eef3fa", stroke="#d6deea", rx=14))
ds = [("SAP", "#C0392B", "#8e2a20", "SAP"),
      ("BigQuery", "#3B7DD8", "#2a5aa0", "BQ"),
      ("Amazon S3", "#E8912A", "#b06d1c", "S3"),
      ("Fabric Native", "#2AA79B", "#1e7a70", "FN")]
dx = 56
for name, fill, stroke, short in ds:
    S.append(rr(dx, 522, 108, 84, shadow=True, rx=10))
    S.append(badge(dx + 54, 548, fill, stroke, short))
    S.append(txt(dx + 54, 592, name, size=12, w=600))
    dx += 118
S.append(rr(56, 616, 468, 34, fill="#ffffff", stroke="#cfd8e4", rx=10))
S.append(ic_onelake(80, 633))
S.append(txt(100, 638, "OneLake", size=14, w=700, anchor="start", fill="#2E7CC4") +
         txt(172, 638, "| Unified Data Foundation", size=13.5, w=500, anchor="start", fill=DARK))

# ============================ M365 COPILOT ====================================
# Copilot Studio group
S.append(rr(584, 150, 442, 140, fill="#ffffff", stroke="#d6deea", opacity=0.65, rx=14))
S.append(logo_copilot(606, 176))
S.append(txt(626, 182, "Copilot Studio", size=14, w=700, anchor="start"))
S.append(tile(600, 196, 190, 82, ["Project Controls", "Agent"], ic_robot))
S.append(tile(812, 196, 196, 82, ["Agent Flows"], ic_flow))

# Work IQ group
S.append(rr(584, 320, 300, 184, fill="#ffffff", stroke="#d6deea", opacity=0.65, rx=14))
S.append(logo_copilot(608, 348))
S.append(txt(628, 354, "Work IQ", size=14, w=700, anchor="start"))
wq = [("Chats", ic_people, 636), ("Meetings", ic_cal, 712),
      ("Emails", ic_mail, 788), ("Documents", ic_word, 856)]
for nm, ic, cx in wq:
    S.append(ic(cx, 404))
    S.append(txt(cx, 434, nm, size=11.5, w=600))
S.append(txt(628, 470, "and more...", size=12.5, w=400, anchor="start", italic=True, fill=GRAY))

# alarm event
S.append(rr(690, 524, 176, 74, shadow=True, rx=12, stroke="#e0b3ad"))
S.append(ic_alarm(716, 548))
S.append(lines(786, 561, ["Commissioning", "Alarm Event"], size=12.5, w=600, gap=15))
S.append(arrow(778, 524, 786, 470))

# cross-section + intra arrows
S.append(arrow(452, 220, 582, 220, double=True))
S.append(arrow(1026, 220, 1078, 220, double=True))
S.append(arrow(690, 292, 690, 318, double=True))
S.append(arrow(902, 292, 858, 388, double=True))

# ============================== FOUNDRY =======================================
# Agent Framework
S.append(rr(1080, 150, 470, 148, fill="#ffffff", stroke="#d6deea", opacity=0.65, rx=14))
S.append(rr(1408, 138, 138, 24, fill="#eef1f6", stroke="#cfd8e4", rx=8))
S.append(txt(1477, 154, "Agent Orchestration", size=11, w=600, fill=GRAY))
S.append(logo_foundry(1104, 178))
S.append(txt(1124, 184, "Agent Framework", size=14, w=700, anchor="start"))
S.append(tile(1098, 198, 204, 88, ["Schedule Risk /", "MPR Agent"],
              lambda a, b: ic_doc(a, b, "#2E7CC4")))
S.append(tile(1328, 198, 204, 88, ["Bid Evaluation", "Agent"],
              lambda a, b: ic_doc(a, b, "#2AA79B")))

# IQ row
S.append(rr(1080, 320, 470, 122, fill="#ffffff", stroke="#d6deea", opacity=0.55, rx=14))
iqs = [("Foundry IQ", ic_search, 1144), ("Azure OpenAI", ic_openai, 1258),
       ("Agent Service", ic_gear, 1372), ("Web IQ", ic_globe, 1486)]
for nm, ic, cx in iqs:
    S.append(rr(cx - 52, 332, 104, 98, shadow=True, rx=10))
    S.append(ic(cx, 362))
    S.append(lines(cx, 404, nm.split(" ") if len(nm) > 10 else [nm], size=12, w=600, gap=14))

# knowledge corpus + storage (below dashed region)
S.append(rr(1076, 470, 474, 188, fill="#f3eef2", stroke="#e0d6de", rx=16))
S.append(tile(1300, 500, 150, 96, ["Knowledge", "Corpus"],
              lambda a, b: ic_doc(a, b, "#7a6aa0")))
S.append(rr(1150, 616, 300, 34, fill="#ffffff", stroke="#cfd8e4", rx=10))
S.append(ic_storage(1178, 633))
S.append(txt(1202, 638, "Azure Storage", size=13.5, w=600, anchor="start"))
S.append(arrow(1375, 500, 1375, 442))
S.append(arrow(1258, 300, 1258, 318, double=True))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "solution_overview.svg")
png_path = os.path.join(here, "solution_overview.png")
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
