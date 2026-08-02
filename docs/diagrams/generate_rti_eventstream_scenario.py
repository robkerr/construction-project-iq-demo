#!/usr/bin/env python3
"""Generate the Real-Time Intelligence (Eventstream) scenario diagram (SVG + PNG).

Left-to-right RTI pipeline for the EPC demo's commissioning-telemetry scenario:
  IIoT producer -> Eventstream (esCommissioning) -> Eventhouse/KQL DB
  (eh_rti_telemetry) -> Real-Time Dashboard + Activator, all on OneLake and
  unified with the batch analytics (same assets, same ontology).
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
def ic_sensor(cx, cy):
    b = "#4a5aa8"
    return (f'<circle cx="{cx}" cy="{cy+4}" r="3" fill="{b}"/>'
            f'<g stroke="{b}" stroke-width="1.8" fill="none">'
            f'<path d="M{cx-6},{cy} q6,-7 12,0"/>'
            f'<path d="M{cx-10},{cy-4} q10,-11 20,0"/></g>')


def ic_stream(cx, cy):
    t = "#1f8f84"
    return "".join(
        f'<path d="M{cx-13+o},{cy-7} L{cx-6+o},{cy} L{cx-13+o},{cy+7}" fill="none" '
        f'stroke="{t}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
        for o in (0, 9, 18))


def ic_db(cx, cy):
    b = "#2568a8"
    return (f'<g fill="#d3e6f7" stroke="{b}" stroke-width="1.6">'
            f'<ellipse cx="{cx}" cy="{cy-8}" rx="11" ry="4"/>'
            f'<path d="M{cx-11},{cy-8} L{cx-11},{cy+8} Q{cx},{cy+13} {cx+11},{cy+8} L{cx+11},{cy-8}"/></g>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="11" ry="4" fill="none" stroke="{b}" stroke-width="1.3"/>'
            f'<path d="M{cx+1},{cy-5} L{cx-4},{cy+1} L{cx+1},{cy+1} L{cx-3},{cy+7}" fill="none" '
            f'stroke="#E8A23D" stroke-width="1.8" stroke-linejoin="round"/>')


def ic_table(cx, cy):
    b = "#2568a8"
    g = [f'<rect x="{cx-11}" y="{cy-9}" width="22" height="18" rx="2" fill="#eaf3fb" '
         f'stroke="{b}" stroke-width="1.4"/>']
    g.append(f'<line x1="{cx-11}" y1="{cy-3}" x2="{cx+11}" y2="{cy-3}" stroke="{b}" stroke-width="1.2"/>')
    g.append(f'<line x1="{cx-11}" y1="{cy+3}" x2="{cx+11}" y2="{cy+3}" stroke="{b}" stroke-width="1"/>')
    g.append(f'<line x1="{cx-3}" y1="{cy-9}" x2="{cx-3}" y2="{cy+9}" stroke="{b}" stroke-width="1"/>')
    return "".join(g)


def ic_mview(cx, cy):
    b = "#2AA79B"
    return (f'<circle cx="{cx}" cy="{cy}" r="10" fill="#e3f5f2" stroke="{b}" stroke-width="1.6"/>'
            f'<path d="M{cx-5},{cy-4} A6,6 0 1 1 {cx-6},{cy+4}" fill="none" stroke="{b}" '
            f'stroke-width="1.8"/><path d="M{cx-7},{cy+1} L{cx-6},{cy+5} L{cx-2},{cy+4}" '
            f'fill="none" stroke="{b}" stroke-width="1.8" stroke-linejoin="round"/>')


def ic_func(cx, cy):
    b = "#6A4FB3"
    return (f'<circle cx="{cx}" cy="{cy}" r="10" fill="#efeafa" stroke="{b}" stroke-width="1.5"/>'
            f'{txt(cx, cy+5, "\u0192(x)", size=10.5, w=700, fill=b)}')


def ic_dash(cx, cy):
    b = "#7A4FB0"
    return (f'<rect x="{cx-12}" y="{cy-10}" width="24" height="20" rx="3" fill="#f2ecfa" '
            f'stroke="{b}" stroke-width="1.6"/>'
            f'<g stroke="{b}" stroke-width="2" stroke-linecap="round">'
            f'<line x1="{cx-7}" y1="{cy+5}" x2="{cx-7}" y2="{cy+1}"/>'
            f'<line x1="{cx-2}" y1="{cy+5}" x2="{cx-2}" y2="{cy-3}"/>'
            f'<line x1="{cx+3}" y1="{cy+5}" x2="{cx+3}" y2="{cy-6}"/></g>')


def ic_bell(cx, cy):
    r = "#C0392B"
    return (f'<path d="M{cx-9},{cy+5} Q{cx-9},{cy-9} {cx},{cy-9} Q{cx+9},{cy-9} {cx+9},{cy+5} Z" '
            f'fill="#f7d7d3" stroke="{r}" stroke-width="1.8"/>'
            f'<line x1="{cx-11}" y1="{cy+5}" x2="{cx+11}" y2="{cy+5}" stroke="{r}" stroke-width="2"/>'
            f'<circle cx="{cx}" cy="{cy+9}" r="2.2" fill="{r}"/>')


def ic_graph(cx, cy):
    g = "#3f8f3f"
    return (f'<g stroke="{g}" stroke-width="1.8">'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx+9}" y2="{cy-4}"/>'
            f'<line x1="{cx-9}" y1="{cy-8}" x2="{cx-6}" y2="{cy+9}"/>'
            f'<line x1="{cx+9}" y1="{cy-4}" x2="{cx-6}" y2="{cy+9}"/></g>'
            f'<circle cx="{cx-9}" cy="{cy-8}" r="3.6" fill="#7BC67B"/>'
            f'<circle cx="{cx+9}" cy="{cy-4}" r="3.6" fill="#7BC67B"/>'
            f'<circle cx="{cx-6}" cy="{cy+9}" r="3.6" fill="#7BC67B"/>')


def ic_app(cx, cy):
    b = "#4a5aa8"
    return (f'<rect x="{cx-12}" y="{cy-10}" width="24" height="20" rx="3" fill="#eceefb" '
            f'stroke="{b}" stroke-width="1.7"/>'
            f'<line x1="{cx-12}" y1="{cy-3}" x2="{cx+12}" y2="{cy-3}" stroke="{b}" stroke-width="1.5"/>'
            f'<circle cx="{cx-8}" cy="{cy-6.5}" r="1.3" fill="{b}"/>'
            f'<circle cx="{cx-4}" cy="{cy-6.5}" r="1.3" fill="{b}"/>')


def ic_bolt(cx, cy):
    return (f'<path d="M{cx+2},{cy-11} L{cx-6},{cy+1} L{cx},{cy+1} L{cx-2},{cy+11} '
            f'L{cx+7},{cy-2} L{cx+1},{cy-2} Z" fill="#E8A23D" stroke="#b8781f" stroke-width="1"/>')


def ic_gear(cx, cy):
    import math
    b = "#7A4FB0"
    teeth = "".join(
        f'<rect x="{cx-2}" y="{cy-13}" width="4" height="5.5" fill="{b}" '
        f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 45))
    return (teeth + f'<circle cx="{cx}" cy="{cy}" r="7.5" fill="#efeafa" stroke="{b}" '
            f'stroke-width="1.8"/><circle cx="{cx}" cy="{cy}" r="2.6" fill="{b}"/>')


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
S.append(txt(860, 52, "Real-Time Intelligence in Microsoft Fabric \u2014 Commissioning Telemetry",
             size=24, w=700))
S.append(txt(860, 80, "Equipment commissioning telemetry streamed, stored, and acted on in "
             "seconds \u2014 unified with batch analytics in OneLake", size=13.5, w=400, fill=GRAY))
# RTI badge
S.append(rr(1420, 96, 244, 34, fill="#ffffff", stroke="#bfe0c8", rx=17, shadow=True))
S.append(ic_bolt(1442, 113))
S.append(txt(1458, 118, "Fabric Real-Time Intelligence", size=12, w=700, anchor="start", fill="#1f8f84"))

# ---- stage geometry ----------------------------------------------------------
CW = 370
xs = [58, 474, 890, 1306]
A1, T1 = "#5b6bb5", "#eef0fa"
A2, T2 = "#2AA79B", "#e6f5f2"
A3, T3 = "#2E7CC4", "#e6f1fb"
A4, T4 = "#7A4FB0", "#f1ebf8"

# STAGE 1 — Source
x = xs[0]
S.append(stage_header(x, CW, A1, T1, ic_sensor, 1, "Source \u00b7 IIoT Telemetry",
                      "Commissioning sensors"))
S.append(stile(x + 8, 226, CW - 16, 92, ic_app, "Commissioning producer",
               [("Custom app \u2192 Event Hubs-compatible send", False),
                ("produce_telemetry.py", True)], accent="#c7cdec"))
S.append(stile(x + 8, 332, CW - 16, 116, ic_bolt, "Fleet \u2014 Project Falcon (PRJ-001)",
               [("ET-1001  hero \u2014 healthy \u25b8 warning \u25b8 ALARM", False),
                ("ET-1002, ET-1003  power transformers", False),
                ("energization / trial-run phases", False)], accent="#c7cdec"))
S.append(stile(x + 8, 462, CW - 16, 116, ic_sensor, "Signals (JSON, ~1/s per asset)",
               [("winding_temp_c \u00b7 top_oil_temp_c \u00b7 load_pct", True),
                ("dga_h2_ppm \u00b7 vibration_mm_s \u00b7 status", True),
                ("event_time \u00b7 equipment_tag \u00b7 project_id", True)], accent="#c7cdec"))

# STAGE 2 — Eventstream
x = xs[1]
S.append(stage_header(x, CW, A2, T2, ic_stream, 2, "Ingest \u00b7 Eventstream",
                      "esCommissioning"))
S.append(stile(x + 8, 226, CW - 16, 100, ic_app, "Custom Endpoint source",
               [("CommissioningApp (Event Hubs API)", False),
                ("secure streaming ingress", False)], accent="#a9ddd5"))
S.append(stile(x + 8, 340, CW - 16, 100, ic_stream, "Stream processing (low / no-code)",
               [("route \u00b7 filter \u00b7 transform events", False),
                ("visual editor, no infra to manage", False)], accent="#a9ddd5"))
S.append(stile(x + 8, 454, CW - 16, 100, ic_db, "Eventhouse destination",
               [("ProcessedIngestion mode", False),
                ("\u2192 KQL DB eh_rti_telemetry", True)], accent="#a9ddd5"))

# STAGE 3 — Eventhouse / KQL
x = xs[2]
S.append(stage_header(x, CW, A3, T3, ic_db, 3, "Store & Analyze \u00b7 Eventhouse",
                      "KQL DB  eh_rti_telemetry"))
S.append(stile(x + 8, 226, CW - 16, 116, ic_table, "commissioning_telemetry", 
               [("landing table \u00b7 streaming ingestion", False),
                ("retention 365d \u00b7 hot cache 30d", False),
                ("JSON mapping telemetry_json", False)], accent="#aacdec", title_mono=True, tsize=12.5))
S.append(stile(x + 8, 356, CW - 16, 78, ic_mview, "latest_by_asset",
               [("materialized view \u2014 arg_max current state", False)],
               accent="#aacdec", title_mono=True, tsize=12.5))
S.append(stile(x + 8, 448, CW - 16, 130, ic_func, "KQL functions", 
               [("winding_temp_anomalies()  \u2014 anomaly ML", True),
                ("dga_trend()  \u2014 incipient-fault H\u2082 trend", True),
                ("active_alarms()  \u2014 assets in alarm", True),
                ("series_decompose_anomalies, sub-second", False)], accent="#aacdec"))

# STAGE 4 — Serve & Act
x = xs[3]
S.append(stage_header(x, CW, A4, T4, ic_dash, 4, "Serve & Act",
                      "Dashboard \u00b7 Alert \u00b7 Agent"))
S.append(stile(x + 8, 226, CW - 16, 116, ic_dash, "Real-Time Dashboard",
               [("rtdCommissioning \u00b7 auto-refresh ~30s", True),
                ("winding-temp & DGA-H\u2082 trends per asset", False),
                ("Active alarms table (ET-1001 live)", False)], accent="#cdb8e2"))
S.append(stile(x + 8, 356, CW - 16, 100, ic_bell, "Activator alert",
               [("actCommissioningAlarms", True),
                ("Email / Teams when asset enters ALARM", False)], accent="#cdb8e2"))
S.append(stile(x + 8, 470, CW - 16, 108, ic_gear, "Operations agent",
               [("summarize alarming asset's context", False),
                ("grounded on the Fabric IQ ontology", False),
                ("acts on the real-time trigger", False)], accent="#cdb8e2", tsize=12.5))

# ---- flow arrows between stages ---------------------------------------------
S.append(flow_arrow(451, 400, "JSON events"))
S.append(flow_arrow(867, 400, "streaming ingestion"))
S.append(flow_arrow(1283, 400, "KQL queries / alerts"))

# ---- OneLake foundation ------------------------------------------------------
S.append(rr(58, 640, 1618, 74, fill="#ffffff", opacity=0.9, stroke="#cfe0ee", rx=14, shadow=True))
S.append(ic_onelake(96, 677))
S.append(txt(120, 671, "OneLake \u2014 one copy, one governance", size=15, w=700, anchor="start",
             fill="#2E7CC4"))
S.append(txt(120, 693, "Real-Time data sits alongside the batch lakehouse (BigQuery, S3, "
             "SQL Server) \u2014 same assets, same ontology, one semantic layer.",
             size=12, w=400, anchor="start", fill=GRAY))
S.append(rr(1230, 650, 430, 54, fill="#eef7f4", stroke="#bfe0c8", rx=10))
S.append(ic_graph(1258, 677))
S.append(txt(1282, 672, "Fabric IQ ontology / Digital Twin Builder", size=12, w=700,
             anchor="start", fill="#2f6f3f"))
S.append(txt(1282, 690, "same entities for dashboards, agents & queries", size=10.8, w=400,
             anchor="start", fill=GRAY))

# ---- loop callout ------------------------------------------------------------
S.append(rr(58, 738, 1618, 46, fill="#fff6ec", stroke="#e7c79a", rx=12))
S.append(ic_bolt(88, 761))
S.append(txt(110, 766, "Closes the loop:", size=13, w=700, anchor="start", fill="#b8781f"))
S.append(txt(238, 766, "the live ET-1001 commissioning ALARM reproduces batch emergency work "
             "order WO-900001 \u2014 one asset, real-time + batch, the same story.",
             size=12.5, w=400, anchor="start", fill="#5b4a2a"))

# ---- presenter note ----------------------------------------------------------
S.append(txt(860, 832, "Demo: kick off run_demo_burst.sh so ET-1001 ramps mid-story; the "
             "Activator alert lands in ~1\u20132 min and the dashboard auto-refreshes.",
             size=12, w=400, italic=True, fill=GRAY))

S.append("</svg>")
svg_text = "\n".join(S)

here = os.path.dirname(os.path.abspath(__file__))
svg_path = os.path.join(here, "rti_eventstream_scenario.svg")
png_path = os.path.join(here, "rti_eventstream_scenario.png")
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
