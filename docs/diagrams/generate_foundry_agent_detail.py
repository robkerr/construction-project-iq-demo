#!/usr/bin/env python3
"""Generate a detailed 'Foundry agent in context' architecture diagram (SVG + PNG).

Shows one Microsoft Foundry agent and how it:
  - grounds on the public web via Web IQ (tool)
  - ties into Microsoft Fabric two ways: Fabric MCP endpoint (tool) and
    Fabric IQ ontology (knowledge source)
  - is consumed by a custom app, Microsoft 365 Copilot, or agent-to-agent
  - is governed by Microsoft Agent 365
"""
import os

W, H = 1680, 812
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
    it = ' font-style="italic"' if italic else ''
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" '
            f'text-anchor="{anchor}" fill="{fill}" '
            f'font-family="Segoe UI, Arial, sans-serif"{it}>{s}</text>')


def conn(x1, y1, x2, y2, label=None, color="#8391a3", sw=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    g = [f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" '
         f'stroke-width="{sw}" marker-end="url(#aend)" marker-start="url(#astart)"{d}/>']
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        wd = len(label) * 6.0 + 14
        g.append(rr(mx - wd / 2, my - 10, wd, 20, fill="#ffffff", stroke="#e2e8f1", rx=10))
        g.append(txt(mx, my + 4, label, size=10.5, w=600, fill=GRAY))
    return "".join(g)


# -------------------------------------------------------------------- icons ---
def _hex(cx, cy, r, fill, stroke):
    import math
    pts = " ".join(f"{cx + r*math.cos(math.radians(a)):.1f},"
                   f"{cy + r*math.sin(math.radians(a)):.1f}" for a in range(0, 360, 60))
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'


def ic_globe(cx, cy):
    b = "#2A6FB0"
    return (f'<circle cx="{cx}" cy="{cy}" r="11" fill="#d6ecfb" stroke="{b}" stroke-width="1.8"/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="5" ry="11" fill="none" stroke="{b}" stroke-width="1.4"/>'
            f'<line x1="{cx-11}" y1="{cy}" x2="{cx+11}" y2="{cy}" stroke="{b}" stroke-width="1.4"/>')


def ic_graph(cx, cy):
    g = "#3f8f3f"
    return (f'<g stroke="{g}" stroke-width="1.8">'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx+9}" y2="{cy-4}"/>'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx-6}" y2="{cy+9}"/>'
            f'<line x1="{cx+9}" y1="{cy-4}" x2="{cx-6}" y2="{cy+9}"/></g>'
            f'<circle cx="{cx-9}" cy="{cy-8}" r="4" fill="#7BC67B"/>'
            f'<circle cx="{cx+9}" cy="{cy-4}" r="4" fill="#7BC67B"/>'
            f'<circle cx="{cx-6}" cy="{cy+9}" r="4" fill="#7BC67B"/>')


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


def ic_doc(cx, cy, accent="#5b6472"):
    return (f'<rect x="{cx-10}" y="{cy-12}" width="20" height="24" rx="2" fill="#f2f5f9" '
            f'stroke="{accent}" stroke-width="1.6"/>'
            f'<g stroke="{accent}" stroke-width="1.5">'
            f'<line x1="{cx-6}" y1="{cy-5}" x2="{cx+6}" y2="{cy-5}"/>'
            f'<line x1="{cx-6}" y1="{cy}" x2="{cx+6}" y2="{cy}"/>'
            f'<line x1="{cx-6}" y1="{cy+5}" x2="{cx+2}" y2="{cy+5}"/></g>')


def ic_gear(cx, cy):
    import math
    b = "#2A6FB0"
    teeth = "".join(
        f'<rect x="{cx-2}" y="{cy-14}" width="4" height="6" fill="{b}" '
        f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 45))
    return (teeth + f'<circle cx="{cx}" cy="{cy}" r="8" fill="#cfe3f5" stroke="{b}" '
            f'stroke-width="2"/><circle cx="{cx}" cy="{cy}" r="3" fill="{b}"/>')


def ic_onelake(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="#2E7CC4"/>'
            f'<path d="M{cx-8},{cy+2} q8,-9 16,0" fill="none" stroke="#fff" stroke-width="2.4"/>'
            f'<path d="M{cx-8},{cy+7} q8,-9 16,0" fill="none" stroke="#cfe6fb" stroke-width="2"/>')


def ic_plug(cx, cy):  # MCP endpoint / connector
    b = "#B7791F"
    return (f'<rect x="{cx-11}" y="{cy-8}" width="15" height="16" rx="4" fill="#fbeecd" '
            f'stroke="{b}" stroke-width="1.8"/>'
            f'<g stroke="{b}" stroke-width="2.4" stroke-linecap="round">'
            f'<line x1="{cx+4}" y1="{cy-3}" x2="{cx+12}" y2="{cy-3}"/>'
            f'<line x1="{cx+4}" y1="{cy+3}" x2="{cx+12}" y2="{cy+3}"/></g>'
            f'<line x1="{cx-11}" y1="{cy}" x2="{cx-15}" y2="{cy}" stroke="{b}" stroke-width="2.4"/>')


def ic_app(cx, cy):
    b = "#2E7CC4"
    return (f'<rect x="{cx-12}" y="{cy-10}" width="24" height="20" rx="3" fill="#eaf3fc" '
            f'stroke="{b}" stroke-width="1.8"/>'
            f'<line x1="{cx-12}" y1="{cy-3}" x2="{cx+12}" y2="{cy-3}" stroke="{b}" stroke-width="1.6"/>'
            f'<circle cx="{cx-8}" cy="{cy-6.5}" r="1.4" fill="{b}"/>'
            f'<circle cx="{cx-4}" cy="{cy-6.5}" r="1.4" fill="{b}"/>')


def ic_copilot(cx, cy):
    return (f'<circle cx="{cx}" cy="{cy}" r="12" fill="url(#cop)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="5" fill="#fff" fill-opacity="0.85"/>')


def _robohead(cx, cy, fill, stroke):
    return (f'<rect x="{cx-7}" y="{cy-6}" width="14" height="12" rx="3.5" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>'
            f'<circle cx="{cx-2.5}" cy="{cy}" r="1.6" fill="{stroke}"/>'
            f'<circle cx="{cx+2.5}" cy="{cy}" r="1.6" fill="{stroke}"/>'
            f'<line x1="{cx}" y1="{cy-6}" x2="{cx}" y2="{cy-9}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<circle cx="{cx}" cy="{cy-10}" r="1.4" fill="{stroke}"/>')


def ic_two_agents(cx, cy):
    return (_robohead(cx - 8, cy - 2, "#d9ccf2", "#6A4FB3") +
            _robohead(cx + 8, cy + 2, "#cfe3f5", "#2A6FB0") +
            f'<path d="M{cx-3},{cy+8} L{cx+3},{cy+8}" stroke="#8391a3" stroke-width="1.8" '
            f'marker-end="url(#aend)" marker-start="url(#astart)"/>')


def ic_shield(cx, cy):
    b = "#3457b2"
    return (f'<path d="M{cx},{cy-11} L{cx+9},{cy-7} L{cx+9},{cy+2} Q{cx+9},{cy+9} {cx},{cy+12} '
            f'Q{cx-9},{cy+9} {cx-9},{cy+2} L{cx-9},{cy-7} Z" fill="#e8eefb" stroke="{b}" stroke-width="1.8"/>'
            f'<path d="M{cx-4},{cy} L{cx-1},{cy+4} L{cx+5},{cy-4}" fill="none" stroke="{b}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')


def ic_layers(cx, cy):
    b = "#6A4FB3"
    return (f'<g fill="#e2d9f4" stroke="{b}" stroke-width="1.4">'
            f'<polygon points="{cx},{cy-9} {cx+11},{cy-4} {cx},{cy+1} {cx-11},{cy-4}"/>'
            f'<polygon points="{cx},{cy-2} {cx+11},{cy+3} {cx},{cy+8} {cx-11},{cy+3}" fill="#d0c2ec"/></g>')


def logo_fabric(cx, cy):
    return (f'<polygon points="{cx-9},{cy} {cx-3},{cy-8} {cx+2},{cy} {cx-3},{cy+8}" fill="#2AA79B"/>'
            f'<polygon points="{cx-1},{cy-2} {cx+5},{cy-10} {cx+10},{cy-2} {cx+5},{cy+6}" fill="#57C4B6"/>')


def logo_foundry(cx, cy):
    return _hex(cx, cy, 12, "url(#fdy)", "#5b3fa0")


# ------------------------------------------------------ composite helpers -----
def chip(x, y, w, h, icon, title, sub=None, stroke="#c9d2de", tsize=13.5, fill="#ffffff"):
    cy = y + h / 2
    g = [rr(x, y, w, h, fill=fill, shadow=True, stroke=stroke)]
    g.append(icon(x + 28, cy))
    ty = cy - 4 if sub else cy + 4
    g.append(txt(x + 52, ty, title, size=tsize, w=700, anchor="start"))
    if sub:
        g.append(txt(x + 52, cy + 16, sub, size=11.5, w=400, anchor="start", fill=GRAY))
    return "".join(g)


def panel_hdr(x, y, s):
    return txt(x, y, s, size=13, w=700, anchor="start", fill="#3a4557")


# ------------------------------------------------------------------ assemble --
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Arial, sans-serif">']
S.append('<defs>'
         '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#eef4fb"/><stop offset="1" stop-color="#f6eff3"/></linearGradient>'
         '<linearGradient id="cop" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#3ab0e6"/><stop offset="0.5" stop-color="#8a63d2"/>'
         '<stop offset="1" stop-color="#e0568f"/></linearGradient>'
         '<linearGradient id="fdy" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="#9a6ff0"/><stop offset="1" stop-color="#6a3fd0"/></linearGradient>'
         '<marker id="aend" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8391a3"/></marker>'
         '<marker id="astart" viewBox="0 0 10 10" refX="1.5" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto-start-reverse"><path d="M10,0 L0,5 L10,10 z" fill="#8391a3"/></marker>'
         '<filter id="sh" x="-20%" y="-20%" width="140%" height="140%">'
         '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#000" flood-opacity="0.13"/></filter>'
         '</defs>')
S.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#bg)"/>')

# ---- title -------------------------------------------------------------------
S.append(txt(840, 50, "Foundry Agent in Context \u2014 Grounding \u00b7 Consumption \u00b7 Governance",
             size=23, w=700))
S.append(txt(840, 76, "How a Microsoft Foundry agent grounds on Fabric and the web, is consumed, and is governed",
             size=13.5, w=400, fill=GRAY))

# ---- column headers ----------------------------------------------------------
S.append(txt(245, 236, "Grounding Sources", size=14, w=700, fill="#3a4557"))
S.append(txt(1420, 236, "Consumption Channels", size=14, w=700, fill="#3a4557"))

# =========================== GOVERNANCE (top) ================================
S.append(rr(552, 108, 576, 58, shadow=True, stroke="#c9c0e0", rx=14))
S.append(ic_shield(586, 137))
S.append(txt(614, 132, "Microsoft Agent 365", size=15, w=700, anchor="start"))
S.append(txt(614, 152, "Registry \u00b7 Identity \u00b7 Security \u00b7 Observability \u00b7 Lifecycle",
             size=11.5, w=400, anchor="start", fill=GRAY))

# =========================== FOUNDRY BOUNDARY ================================
S.append(rr(470, 190, 720, 548, fill="#ffffff", opacity=0.35, stroke="#9a8fc4",
            sw=1.6, rx=18, dash="7 6"))
S.append(rr(486, 198, 232, 38, shadow=True, rx=10, stroke="#d8d1ea"))
S.append(logo_foundry(510, 217))
S.append(txt(532, 222, "Microsoft Foundry", size=13.5, w=700, anchor="start"))

# ---- the agent card ----------------------------------------------------------
S.append(rr(510, 250, 640, 474, shadow=True, stroke="#b9c4d4", sw=1.8, rx=16))
S.append(logo_foundry(542, 286))
S.append(txt(568, 280, "Schedule Risk / MPR Agent", size=16, w=700, anchor="start"))
S.append(txt(568, 300, "Azure AI Foundry Agent", size=11.5, w=400, anchor="start", fill=GRAY))
S.append(f'<line x1="528" y1="316" x2="1132" y2="316" stroke="#e3e8ef" stroke-width="1.4"/>')

# left: Tools + Knowledge
S.append(rr(528, 330, 300, 218, fill="#f6f9fd", stroke="#dbe3ee", rx=12))
S.append(panel_hdr(548, 354, "Tools"))
S.append(chip(544, 366, 268, 76, ic_globe, "Web IQ", "Live web content &amp; search"))
S.append(chip(544, 452, 268, 76, ic_plug, "Fabric MCP Endpoint", "Direct Fabric tool calls",
              stroke="#e2c98f"))
S.append(rr(528, 566, 300, 150, fill="#f6f9fd", stroke="#dbe3ee", rx=12))
S.append(panel_hdr(548, 590, "Knowledge (Grounding)"))
S.append(chip(544, 602, 268, 96, ic_graph, "Fabric IQ (Ontology)", "Grounded enterprise knowledge",
              stroke="#bfe0bf"))

# right: model / instructions / runtime / memory
S.append(chip(848, 330, 288, 82, ic_openai, "Reasoning Model", "Azure OpenAI \u00b7 GPT-4o"))
S.append(chip(848, 424, 288, 82, lambda a, b: ic_doc(a, b, "#2E7CC4"), "Instructions",
              "Schedule-risk analysis &amp; MPR"))
S.append(chip(848, 518, 288, 82, ic_gear, "Foundry Agent Service", "Orchestration &amp; threads"))
S.append(chip(848, 612, 288, 82, ic_layers, "Threads &amp; Memory", "Conversation state"))

# =========================== GROUNDING (left) ================================
# public web
S.append(rr(70, 250, 350, 150, shadow=True, stroke="#c9d2de", rx=14))
S.append(txt(90, 280, "Public Web", size=12.5, w=700, anchor="start", fill="#3a4557"))
S.append(ic_globe(118, 340))
S.append(txt(150, 334, "Internet Content", size=15, w=700, anchor="start"))
S.append(txt(150, 356, "Standards, news, supplier &amp; market data", size=11.5, w=400,
             anchor="start", fill=GRAY))

# microsoft fabric group (two integration modes)
S.append(rr(70, 430, 350, 322, fill="#eef7f1", stroke="#bfe0c8", rx=16))
S.append(logo_fabric(100, 462))
S.append(txt(124, 468, "Microsoft Fabric", size=14, w=700, anchor="start"))
S.append(chip(88, 486, 314, 92, ic_plug, "Fabric MCP Server", "Query tools over OneLake",
              stroke="#e2c98f"))
S.append(chip(88, 590, 314, 92, ic_graph, "Fabric IQ (Ontology)", "Semantic knowledge layer",
              stroke="#bfe0bf"))
S.append(rr(88, 700, 314, 36, fill="#ffffff", stroke="#cfd8e4", rx=10))
S.append(ic_onelake(112, 718))
S.append(txt(136, 723, "OneLake", size=13, w=700, anchor="start", fill="#2E7CC4"))

# grounding connectors
S.append(conn(420, 336, 544, 402, "web"))
S.append(conn(402, 532, 544, 490, "MCP tool"))
S.append(conn(402, 636, 544, 650, "knowledge"))

# =========================== CONSUMPTION (right) =============================
S.append(chip(1230, 300, 380, 92, ic_app, "Custom Application", "Foundry SDK / REST API",
              tsize=14.5))
S.append(chip(1230, 414, 380, 92, ic_copilot, "Microsoft 365 Copilot", "Declarative agent / plugin",
              tsize=14.5))
S.append(chip(1230, 528, 380, 92, ic_two_agents, "Agent-to-Agent (A2A)", "Multi-agent orchestration",
              tsize=14.5))

# consumption fan-out from agent right edge
S.append(conn(1150, 470, 1230, 346, "invokes"))
S.append(conn(1150, 470, 1230, 460, "invokes"))
S.append(conn(1150, 470, 1230, 574, "invokes"))

# governance connector
S.append(conn(838, 166, 838, 250, "manages", dash="5 5"))

# ---- caption -----------------------------------------------------------------
S.append(rr(470, 756, 740, 34, fill="#ffffff", opacity=0.85, stroke="#e2e8f1", rx=10))
S.append(txt(840, 778,
             "Fabric integrates two ways \u2014 as an MCP tool (live queries) and as a "
             "Fabric IQ knowledge source (semantic grounding).",
             size=12.5, w=600, fill="#3a4557"))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "foundry_agent_detail.svg")
png_path = os.path.join(here, "foundry_agent_detail.png")
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
