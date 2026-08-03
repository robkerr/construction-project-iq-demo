#!/usr/bin/env python3
"""Generate the demo-scenario pre-brief diagram (SVG + PNG).

A presenter pre-brief of the four day-in-the-life scenarios from demo_flow.md:
each persona's trigger (why they engage), their path through the solution, and
the outcome -- all hung on the shared hero thread (Falcon / ET-1001 / the
high-risk supplier). Cards are ordered in demo (chronological) sequence.
"""
import os

W, H = 1760, 812
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


def txt(x, y, s, size=14, w=400, anchor="middle", fill=DARK, italic=False):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    it = ' font-style="italic"' if italic else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" '
            f'text-anchor="{anchor}" fill="{fill}" '
            f'font-family="Segoe UI, Arial, sans-serif"{it}>{s}</text>')


def wrap(s, n=40):
    words, lines, cur = s.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + (1 if cur else 0) <= n:
            cur = (cur + " " + wd).strip()
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# -------------------------------------------------------------------- icons ---
def ic_person(cx, cy, c):
    return (f'<circle cx="{cx}" cy="{cy}" r="17" fill="{c}"/>'
            f'<circle cx="{cx}" cy="{cy-4}" r="5.5" fill="#ffffff"/>'
            f'<path d="M{cx-9},{cy+12} Q{cx-9},{cy+2} {cx},{cy+2} Q{cx+9},{cy+2} {cx+9},{cy+12} Z" '
            f'fill="#ffffff"/>')


def ic_cal(cx, cy, c):
    return (f'<rect x="{cx-10}" y="{cy-9}" width="20" height="18" rx="3" fill="none" '
            f'stroke="{c}" stroke-width="2"/>'
            f'<line x1="{cx-10}" y1="{cy-3}" x2="{cx+10}" y2="{cy-3}" stroke="{c}" stroke-width="2"/>'
            f'<line x1="{cx-4}" y1="{cy-13}" x2="{cx-4}" y2="{cy-7}" stroke="{c}" stroke-width="2"/>'
            f'<line x1="{cx+4}" y1="{cy-13}" x2="{cx+4}" y2="{cy-7}" stroke="{c}" stroke-width="2"/>')


def ic_bell(cx, cy, c):
    return (f'<path d="M{cx-9},{cy+5} Q{cx-9},{cy-9} {cx},{cy-9} Q{cx+9},{cy-9} {cx+9},{cy+5} Z" '
            f'fill="none" stroke="{c}" stroke-width="2"/>'
            f'<line x1="{cx-11}" y1="{cy+5}" x2="{cx+11}" y2="{cy+5}" stroke="{c}" stroke-width="2"/>'
            f'<circle cx="{cx}" cy="{cy+9}" r="2.2" fill="{c}"/>')


def ic_doc(cx, cy, c):
    return (f'<rect x="{cx-9}" y="{cy-11}" width="18" height="22" rx="2" fill="none" '
            f'stroke="{c}" stroke-width="2"/>'
            f'<g stroke="{c}" stroke-width="1.7"><line x1="{cx-5}" y1="{cy-5}" x2="{cx+5}" y2="{cy-5}"/>'
            f'<line x1="{cx-5}" y1="{cy}" x2="{cx+5}" y2="{cy}"/>'
            f'<line x1="{cx-5}" y1="{cy+5}" x2="{cx+2}" y2="{cy+5}"/></g>')


def ic_q(cx, cy, c):
    return (f'<circle cx="{cx}" cy="{cy}" r="11" fill="none" stroke="{c}" stroke-width="2"/>'
            f'{txt(cx, cy+5, "?", size=15, w=700, fill=c)}')


def ic_check(cx, cy, c):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="#ffffff" stroke="{c}" stroke-width="1.8"/>'
            f'<path d="M{cx-5},{cy} L{cx-1},{cy+4} L{cx+6},{cy-5}" fill="none" stroke="{c}" '
            f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')


def ic_bolt(cx, cy):
    return (f'<path d="M{cx+3},{cy-13} L{cx-7},{cy+1} L{cx},{cy+1} L{cx-3},{cy+13} '
            f'L{cx+8},{cy-2} L{cx+1},{cy-2} Z" fill="#E8A23D" stroke="#b8781f" stroke-width="1"/>')


def ic_link(cx, cy):
    b = "#2AA79B"
    return (f'<g fill="none" stroke="{b}" stroke-width="2.4" stroke-linecap="round">'
            f'<path d="M{cx-9},{cy+5} a5,5 0 0 1 0,-10 l4,0"/>'
            f'<path d="M{cx+9},{cy-5} a5,5 0 0 1 0,10 l-4,0"/>'
            f'<line x1="{cx-4}" y1="{cy}" x2="{cx+4}" y2="{cy}"/></g>')


def stepnum(cx, cy, n, c):
    return (f'<circle cx="{cx}" cy="{cy}" r="10" fill="{c}"/>'
            f'{txt(cx, cy+4, n, size=11.5, w=700, fill="#ffffff")}')


# ---------------------------------------------------------------- card render --
CW = 388


def slabel(x, y, s, c):
    return txt(x, y, s.upper(), size=10.5, w=700, anchor="start", fill=c)


def render_card(x, dark, tint, ticon, name, role, seg, trigger, steps, outcome):
    g = [rr(x, 200, CW, 504, shadow=True, stroke=dark, sw=1.7, rx=16)]
    # header
    g.append(rr(x, 200, CW, 72, fill=tint, stroke=dark, sw=1.7, rx=16))
    g.append(f'<rect x="{x}" y="248" width="{CW}" height="24" fill="{tint}"/>')
    g.append(ic_person(x + 38, 236, dark))
    g.append(txt(x + 68, 230, name, size=16.5, w=700, anchor="start"))
    g.append(txt(x + 68, 251, role, size=11.5, w=400, anchor="start", fill=GRAY))
    pw = len(seg) * 6.4 + 20
    g.append(rr(x + CW - pw - 14, 212, pw, 22, fill=dark, stroke=dark, rx=11))
    g.append(txt(x + CW - pw / 2 - 14, 227, seg, size=11, w=700, fill="#ffffff"))
    # trigger
    g.append(slabel(x + 22, 300, "Why they engage", dark))
    g.append(ticon(x + 36, 331, dark))
    ty = 320
    for ln in wrap(trigger, 40):
        g.append(txt(x + 58, ty, ln, size=12, w=600, anchor="start"))
        ty += 16
    # path
    g.append(slabel(x + 22, 372, "Path through the solution", dark))
    sy = 388
    for i, st in enumerate(steps, 1):
        g.append(stepnum(x + 36, sy + 16, str(i), dark))
        lines = wrap(st, 40)
        tyy = sy + 12 if len(lines) > 1 else sy + 20
        for ln in lines:
            g.append(txt(x + 58, tyy, ln, size=11.8, w=400, anchor="start", fill="#333b48"))
            tyy += 16
        sy += 64
    # outcome
    g.append(slabel(x + 22, 586, "Outcome", dark))
    g.append(ic_check(x + 36, 614, dark))
    oy = 604
    for ln in wrap(outcome, 40):
        g.append(txt(x + 58, oy, ln, size=12, w=600, anchor="start", fill="#2c3542"))
        oy += 16
    return "".join(g)


# ------------------------------------------------------------------ assemble --
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">']
S.append('<defs>'
         '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#eef4fb"/><stop offset="1" stop-color="#f5eff3"/></linearGradient>'
         '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
         '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.13"/></filter>'
         '</defs>')
S.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>')

# title
S.append(txt(880, 50, "Demo Scenarios at a Glance \u2014 Who Acts, Why, and the Path They Take",
             size=24, w=700))
S.append(txt(880, 78, "A pre-brief of the four day-in-the-life scenarios \u2014 so you already "
             "know each persona's motivation before we run them live", size=13.5, w=400, fill=GRAY))

# hero-thread band
S.append(rr(60, 100, 1640, 80, fill="#fff6ec", stroke="#e7c79a", rx=14, shadow=True))
S.append(ic_bolt(102, 140))
S.append(txt(130, 132, "The hero thread \u2014 one late transformer \u00b7 one risky supplier "
             "\u00b7 one project, seen four ways", size=15.5, w=700, anchor="start", fill="#8a5a12"))
S.append(txt(130, 158, "Project Falcon (PRJ-001)  \u00b7  transformer ET-1001  \u00b7  the supplier's "
             "late PO-00512 is also the disqualified cheapest bid on RFQ-0001", size=12.5, w=400,
             anchor="start", fill="#6a5220"))

# cards (demo / chronological order: Maya, Daniel, Sam, Priya)
xs = [60, 478, 896, 1314]

render_card_args = [
    (xs[0], "#1f8f6f", "#e6f5ef", ic_cal,
     "Maya", "Project Controls Manager \u00b7 LOB", "Seg 1 & 3",
     "Monthly portfolio review \u2014 Project Falcon is the #1 schedule risk (score ~96).",
     ["Executive Portfolio dashboard \u2014 Falcon flags red",
      "Drill to Schedule Risk: SAP late-PO + non-SAP change EC-1207",
      "Ask Copilot \u201cwhy?\u201d \u2192 cited answer, then generate the MPR"],
     "A defensible Monthly Progress Report with real numbers spanning SAP + non-SAP."),

    (xs[1], "#B9631C", "#fbeede", ic_bell,
     "Daniel", "Commissioning / Ops Engineer \u00b7 LOB", "Seg 1",
     "ET-1001 is being energized on site and its telemetry starts to overheat.",
     ["Activator alert: \u201casset entered ALARM\u201d (Teams / email)",
      "Open Real-Time Dashboard \u2014 winding-temp & DGA-H\u2082 climbing live",
      "Same asset as emergency work order WO-900001"],
     "Instant field awareness \u2014 the live symptom of the risk Maya just flagged."),

    (xs[2], "#6A4FB3", "#efeafa", ic_q,
     "Sam", "AI / Data Architect", "Seg 2 & 3",
     "How is all this data unified, and how are the agents kept well-grounded?",
     ["Five sources \u2192 OneLake: mirror \u00b7 shortcut \u00b7 ELT \u00b7 stream",
      "Medallion + fusion tables + ontology (shared vocabulary)",
      "Agents grounded: Fabric IQ + Foundry IQ + Web IQ via MCP"],
     "Agents grounded by construction on one governed semantic model."),

    (xs[3], "#2E6FB5", "#e7f1fb", ic_doc,
     "Priya", "Procurement / Category Mgr \u00b7 SAP", "Seg 3",
     "Award decision due on Falcon transformer RFQ-0001 \u2014 the cheapest bid is high-risk.",
     ["Ask Copilot: run the Technical Bid Evaluation (TBE)",
      "Cheapest bidder disqualified on a mandatory requirement",
      "Commercial Evaluation (CBE) \u2192 award lowest evaluated price"],
     "A justified award \u2014 cheapest \u2260 best value; the disqualified bidder is the late-PO supplier."),
]
for a in render_card_args:
    S.append(render_card(*a))

# payoff strip
S.append(rr(60, 726, 1640, 60, fill="#eef7f4", stroke="#bfe0c8", rx=14, shadow=True))
S.append(ic_link(104, 756))
S.append(txt(134, 748, "Four people \u00b7 four questions \u00b7 one governed answer", size=15,
             w=700, anchor="start", fill="#1f8f6f"))
S.append(txt(134, 770, "The same transformer, supplier, and project \u2014 seen through cost (SAP), "
             "schedule (non-SAP), procurement (bids), and telemetry (RTI), then acted on by AI.",
             size=12.5, w=400, anchor="start", fill="#3a5548"))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "demo_scenarios_prebrief.svg")
png_path = os.path.join(here, "demo_scenarios_prebrief.png")
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
