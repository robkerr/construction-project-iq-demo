# Project Controls IQ — "Art of the Possible" Demo Flow

A presenter's script for the end-to-end demo. It weaves one continuous **hero
thread** (Project **Falcon / PRJ-001** and its main power transformer **ET-1001**)
through four segments so the audience sees the *same* story from four angles:
a business outcome, the data platform beneath it, the AI that reasons over it,
and the wrap-up that ties it together.

> **Everything shown is real and already built** unless a line is tagged
> **`[ENVISIONED]`** (a natural addition we can build if we want it in the
> narrative) or **`[TO BUILD]`** (needs authoring before the demo).

---

## The hero thread (say this once, pay it off four times)

**Project Falcon** is a 230 kV substation project. Its long-lead **main power
transformer ET-1001** is late, over budget, and — during commissioning — starts
to overheat. The **same high-risk supplier** whose late PO (**PO-00510**) drives
Falcon's schedule risk is the **cheapest bidder we disqualified** on the
transformer RFQ. No single system knows this. **Fabric fuses SAP + non-SAP +
real-time telemetry into one governed answer**, and the AI agents act on it.

| Where it shows up | Segment |
|---|---|
| Falcon is the #1 portfolio risk (dashboard + agent writes the MPR) | 1 & 3 |
| ET-1001 telemetry ramps to **alarm** live; ops gets notified | 1 |
| The data came from BigQuery, SQL Server, and Eventstream telemetry — unified in OneLake | 2 |
| Cheapest transformer bid ≠ best value; disqualified supplier = the late-PO supplier | 3 |

---

## Audience map (make sure each person gets "their moment")

| Audience | What they came for | Where they lean in |
|---|---|---|
| **SAP / Application IT** | How SAP + non-SAP data unify without rip-and-replace | Seg 2 (mirroring, shortcuts, ELT), Seg 3 (grounded answers over SAP data) |
| **LOB / Operations** | Faster, better decisions; day-in-the-life | Seg 1 (dashboards, RTI alert, Copilot), Seg 3 (MPR / bid award) |
| **AI Architects / thought leaders** | How to build *well-grounded* agents | Seg 2 (unified layer + **Fabric IQ ontology**), Seg 3 (four ontology-grounded Foundry agents, Fabric IQ + Web IQ, Entra passthrough) |

---

## Cast of personas (day-in-the-life)

- **Maya — Project Controls Manager** (LOB). Owns the portfolio; lives in the
  dashboards; accountable for the Monthly Progress Report (MPR).
- **Daniel — Commissioning / Operations Engineer** (LOB, field). Energizing
  ET-1001 on site; reacts to real-time equipment health.
- **Priya — Procurement / Category Manager** (SAP/Application IT + sourcing).
  Runs competitive RFQs; owns award decisions and supplier risk.
- **Sam — AI / Data Architect** (AI thought leader). Cares how the agents are
  grounded, governed, and composed.

---

# Segment 1 — Fabric as a platform + a business day-in-the-life
*~10–12 min · audience: everyone, LOB-forward*

**Goal:** Lead with outcomes, not architecture. Show that Fabric already brings
the data together and puts answers in front of business users — dashboards,
real-time analytics, an ontology-backed semantic layer, and AI agents — before
we ever open a pipeline.

### 1a. Set the platform frame (2 min)
- One-slide/one-breath framing of Fabric: **one copy of data in OneLake**, every
  workload (Data Engineering, Real-Time Intelligence, Power BI, AI agents)
  reading the *same* governed data. "Everything you're about to see reads one
  governed lakehouse — the dashboards through a **semantic model**, the agents
  through an **ontology**, both over the same gold tables, so they never disagree."

### 1b. Maya's morning — portfolio decision (4 min)
1. Open **Power BI in Fabric → `EPC Demo` → Executive Portfolio Overview**.
   - Global **project map** (lat/lon), portfolio KPI cards (Active Projects,
     Avg % Complete), %-complete and risk bars. Twelve capital projects.
2. **Project Falcon is red.** Drill to **Portfolio Schedule Risk** page — the
   **Schedule Risk Score** (~96) is driven by **both** a SAP signal (late
   long-lead PO + forecast overrun) and a non-SAP signal (an approved engineering
   change). The new **"Why Falcon is red" root-cause band** names them and shows
   they land on the **same work package**: engineering change **EC-1207** (+18
   days, Primavera) and the late long-lead transformer **PO-00510** (SAP) on one WBS.
3. The dashboard tells Maya *what* and *where* — but not the *so-what* across
   systems. → **"⚠ Ask Copilot."** She opens the agent (previewed here,
   deep-dived in Segment 3) and asks what the dashboard **can't** answer: *"What's
   driving Falcon's schedule risk, and what does that late transformer PO mean for
   our sourcing and live field risk?"* → the agent makes the cross-system leap:
   the PO's supplier is the **high-risk supplier we disqualified** as the cheapest
   bidder on the replacement RFQ — and it's the **same transformer (ET-1001)**
   Daniel is about to watch alarm live. Then *"Generate this month's MPR for
   Falcon."* → a house-style report with real numbers. *No single dashboard knows
   all of that; the agent does, because it reads the ontology.*

> **Why it lands:** the dashboard names the root cause *within* project controls;
> the agent adds the cross-system consequence the dashboard can't see. Same gold
> layer, two lenses — foreshadow that Segment 2 shows *where those signals live*.

### 1c. Daniel's alert — real-time operations (4 min)
1. While Maya was talking, **ET-1001 was being commissioned** and its telemetry
   was streaming. Daniel receives an **Activator** notification
   (`actCommissioningAlarms`, email/Teams) — *"a commissioning asset entered
   ALARM."*
2. He opens the **Real-Time Dashboard `rtdCommissioning`**: winding-temperature
   and dissolved-gas (H₂) trends per asset, and an **Active alarms** table.
   **ET-1001** is climbing past commissioning thresholds live.
3. Tie the loop: this real-time event **reproduces emergency work order
   WO-900001** — the physical symptom of the *same* late, troubled transformer
   Maya just flagged. Real-time + batch, same asset, same story.

> **Presenter setup:** kick off `external_sources/rti_commissioning/run_demo_burst.sh`
> a couple of minutes before this so ET-1001 is mid-ramp. Alert lands ~1–2 min
> after alarm; dashboard auto-refreshes ~30s.

### 1d. The through-line: one gold layer, two lenses (1–2 min)
- Both Maya's dashboard and Daniel's real-time view resolve to the **same
  business entities** — Project, Work Package, **Equipment/Asset (ET-1001)**,
  Supplier, PO, Permit, Work Order.
- **Two lenses, one gold layer.** The **ProjectControlsIQ semantic model**
  (Direct Lake) is what Maya's dashboard reads; the **`EPCOntology`** ontology
  (**Fabric IQ**) is what Segment 3's agents read. Both are modeled **once** over
  the *same* lakehouse `silver`/`gold` tables, so every dashboard, agent, and
  query speaks the same language and the numbers always reconcile. Segment 2 shows
  how both are built; Segment 3's agents ground directly on the ontology.

**Segment 1 takeaway:** *Business users already get analytics, real-time
operations, and AI answers — on data that's been brought together for them.*

---

# Segment 2 — The unified data platform (where the data comes from)
*~10–12 min · audience: SAP/Application IT-forward, Architects*

**Goal:** Put a concrete, visual picture around the "unified data layer"
marketing. Show the **four ingestion patterns** feeding one bronze/silver/gold
lakehouse — *where* each source lives and *how* it's wired, at a high level. You
won't configure anything live; you'll open the finished config and narrate it.

### 2a. The unified-layer picture (2 min)
Draw/return to a single diagram: **four sources (plus a live telemetry stream)
→ OneLake bronze → silver → gold → a semantic model (dashboards) and an ontology
(agents) → business users.**

| # | Source system | Subject | Into Fabric via |
|---|---|---|---|
| 1 | **Fabric-native** lakehouse | Project controls (schedule, EC, bids) **+ permits & inspections** | **Native** Delta in OneLake |
| 2 | **SAP** (S/4HANA) | Suppliers, POs, cost | **ELT pipeline** → `Files/landing` → notebooks |
| 3 | Google **BigQuery** | Work-order management | **Mirroring** → OneLake **shortcut** in bronze |
| 4 | On-prem **SQL Server** | Time clock / labor | **Mirroring** → OneLake **shortcut** in bronze |
| 5 | **Eventstream** (custom app) | Equipment commissioning telemetry (IIoT) | **RTI** → KQL Database (Eventhouse) |

Four headline patterns side by side: **native** governed Delta, **mirroring**
(near-real-time replication surfaced as a zero-copy **OneLake shortcut**),
**ELT pipeline** (Copy + notebook orchestration), and **RTI** (event stream →
KQL).

### 2b. Mirroring — SAP-adjacent and operational systems (3 min)
- Open a **mirrored database** item (BigQuery work orders and/or SQL Server time
  clock). Narrate: Fabric **replicates** the source continuously into OneLake as
  Delta — no ETL to maintain, near-real-time, and it lands as a **shortcut in
  bronze** so it's queryable next to everything else.
- **SAP angle:** this is the pattern for keeping SAP/operational data current in
  the analytics layer *without* rip-and-replace or brittle nightly extracts.

### 2c. Shortcuts — zero-copy virtualization (2 min)
- Open a **OneLake shortcut** in bronze that points at the **mirrored** BigQuery
  / SQL Server tables. Narrate: **the data never moved** — Fabric points at the
  Delta already in OneLake and it behaves like a native lakehouse table. Zero
  copies, one governed namespace, instant fusion on `project_id` /
  `equipment_tag`.

### 2d. ELT pipeline — the traditional path, still first-class (2 min)
- Open **`PL_ELT_Landing_to_Gold`**: Copy raw Parquet extracts → `Files/landing`
  → run notebooks `02_load_bronze` → `03_build_silver_gold`. Narrate: when you
  *do* want a classic, orchestrated ingest (e.g., SAP / core landing data), it's
  right here alongside the zero-copy patterns — same destination lakehouse.

### 2e. Medallion + the fused answer (2 min)
- Show `bronze → silver → gold`. Call out the **fusion tables** that only exist
  because the sources are unified:
  `gold.project_schedule_risk`, `gold.bid_evaluation`,
  `gold.rfq_award_recommendation` (plus `at_risk_activities`, `late_procurement`).
- **`dim_wbs` is the SAP ↔ non-SAP bridge** — the work-package key that lets the
  **Schedule Risk Score** combine a SAP late-PO/overrun with a non-SAP
  change/float slip on the *same* work package.
- **Fabric IQ ontology (`EPCOntology`) — built** — lands here technically: the
  entities and relationships (Project → WBS → Work Orders / POs / Engineering
  Changes; Project → Bids → Suppliers; Project → Permits → Inspections) are
  modeled **once** over `silver`/`gold`. The **semantic model** exposes those same
  gold tables to Power BI; the **ontology** exposes them to the Foundry agents as
  **Fabric IQ** — one governed layer, two lenses, so Segment 3's agents are
  well-grounded by construction.

**Segment 2 takeaway:** *One lakehouse, many front doors (native, mirror,
shortcut, pipeline, stream). Fabric-native project controls + permits, SAP,
BigQuery, SQL Server, and IIoT telemetry all become one governed, queryable
model — read by dashboards through a **semantic model** and by agents through the
**`EPCOntology`** (Fabric IQ), two lenses over the same gold layer.*

---

# Segment 3 — Agentic AI on the unified data layer
*~13–16 min · audience: AI Architects-forward, LOB for the payoff*

**Goal:** Show that the unified/governed layer is exactly what makes
**well-grounded** agents easy to build — and demonstrate the AI scenarios (two of
which *also* produced the Power BI reports) that run on four ontology-grounded
Foundry agents.

### 3a. How the agents are grounded (3 min — architecture)
- **Fabric IQ = the `EPCOntology` ontology (built).** It's the structured,
  numeric source of truth for the agents — modeled over the **same**
  `silver`/`gold` tables the dashboards' **ProjectControlsIQ semantic model**
  exposes (Schedule Risk Score, Risk Band, TBE/CBE, evaluated price) — so the
  agents and the dashboards can never disagree.
- **Four purpose-built Azure AI Foundry agents** (`gpt-4.1`), each owning one
  scenario/persona and all grounded the **same** way:
  - `epc-monthly-progress-report` — **Maya's** MPR.
  - `epc-technical-bid-evaluation` — **Priya's** TBE.
  - `epc-commercial-bid-evaluation` — **Priya's** CBE (downstream of the TBE).
  - `epc-change-notice` — **Project Controls'** formal change notice.
- **Grounding pattern (the Architect payoff):** each agent calls the native
  **`fabric_iq`** tool, which reaches the ontology's **MCP endpoint** — *no*
  stored secret and *no* data copy. It uses **`UserEntraToken` passthrough**, so
  the **caller's own identity** hits Fabric and **Fabric RBAC is enforced per
  request**. Every number comes from the ontology; the agents never invent one.
- **Web IQ** — an optional `web_search` tool for external context (what a
  datasheet parameter or Incoterm means) — never for project figures.
- **`[ENVISIONED]` Foundry IQ** — the Phase-4 Azure AI Search **knowledge
  corpus** (authoring standards, escalation policy, prior MPRs / TBE-CBE, supplier
  quotations) is built and can be layered in as a second tool when an agent needs
  house-style or document grounding alongside the ontology's numbers.
- **Consumption:** the agents are called over the standards-based **Responses
  API** (Entra auth), so the *same* agent serves a Copilot/CLI session, a Teams /
  Copilot surface, or a lightweight web app — business users consume it where they
  already work.

### 3b. AI Scenario 1 — Portfolio schedule risk → MPR (4 min)
*Agent: **`epc-monthly-progress-report`** (Maya) — also produced the **Portfolio
Schedule Risk** report.*
1. *"What's driving Falcon's schedule risk, and what does the late transformer PO
   mean for our sourcing and field risk?"* → the dashboard already **named** the
   collision (EC-1207 + PO-00510 on one WBS); the agent goes **past** it — fusing
   SAP (late **PO-00510**, ~$1.1M overrun) + non-SAP (**EC-1207**) and then making
   the leap the dashboard can't: the PO's supplier is the **high-risk supplier we
   disqualified** as the cheapest bidder on the replacement RFQ (Scenario 2), and
   it owns the **ET-1001** transformer alarming live (Segment 1). Every figure is
   pulled from **Fabric IQ**.
2. *"Generate this month's MPR for Falcon."* → full report in house style, real
   numbers — the artifact Maya needed in Segment 1: **Red** band + escalation.
3. Point back: *the agent reads the **ontology**, the dashboard reads the
   **semantic model** — two lenses over the same gold layer, so their numbers
   reconcile to the cent.*

### 3c. AI Scenario 2 — Bid evaluation TBE → CBE (5 min)
*Agents: **`epc-technical-bid-evaluation`** → **`epc-commercial-bid-evaluation`**
(Priya) — also produced the **Bid Evaluation** report.*
1. *"Run the technical bid evaluation for the Falcon transformer (RFQ-0001)."* →
   **TBE**: weighted compliance vs the datasheet (scored from **Fabric IQ**); the
   **cheapest** bidder (a **high-risk** supplier) is **disqualified** on a
   mandatory requirement.
2. *"Now the commercial evaluation — who do we award, and why not the cheapest?"*
   → **CBE**: quotes normalized to an **evaluated price** (spares, freight,
   schedule-delay, financing, warranty loadings); award goes to the lowest
   *evaluated* price among *qualified* bidders.
3. **Payoff tie-back:** the disqualified cheapest supplier is the **same
   high-risk supplier** whose late transformer PO drives Falcon's schedule risk
   in Scenario 1 — and whose asset (ET-1001) alarmed in Segment 1. One supplier,
   one asset, one project — seen by cost, schedule, engineering, and telemetry
   at once.

### 3d. AI Scenario 3 — Draft the change notice (2 min)
*Agent: **`epc-change-notice`** (Project Controls).*
1. *"Draft the change notice for EC-1207 on Falcon."* → a formal change notice
   that fuses the approved **engineering change EC-1207** with the **late
   long-lead transformer PO (PO-00510)** on the **same WBS** — the paperwork the
   MPR's cross-system finding implies, generated in seconds and grounded in
   **Fabric IQ**.
2. Tie-back: same EC, same PO, same supplier as Scenarios 1–2 — the ontology
   makes every agent tell one consistent story.

> **Presenter note:** `epc-change-notice` retrieves the numbers from Fabric IQ
> correctly, but `gpt-4.1` can occasionally re-shape ids/dates/names while
> drafting — prefer the pinned-hero-facts build for a live audience, or lead with
> the MPR/TBE/CBE agents (dollar-figure-heavy, rock-solid) for a zero-risk run.

### 3e. `[ENVISIONED]` Operations agent closing the real-time loop (1–2 min)
- Frame the Segment 1 Activator alert as an **operations agent** pattern: a
  real-time trigger (ET-1001 alarm) that can **notify, summarize the asset's
  cross-system context** (open PO, permits, work order, supplier risk) via the
  same **Fabric IQ** ontology grounding, and recommend the next action. Show the
  alert; if we build the summarizer action, demo it here.

**Segment 3 takeaway:** *Because the data is unified and governed by the
`EPCOntology`, four Foundry agents are grounded by construction — **Fabric IQ**
for the numbers (per-caller Entra passthrough + Fabric RBAC), **Web IQ** for the
world (and **Foundry IQ** for documents when needed) — and consumed over the
Responses API in Teams/Copilot or a web app.*

---

# Segment 4 — Wrap-up (tie it all together)
*~3–4 min · audience: everyone*

1. **Replay the hero thread in one sentence:** *One late transformer from one
   risky supplier showed up in cost (SAP), schedule (non-SAP), procurement
   (bids), and the field (real-time telemetry) — and Fabric turned four silos
   into one answer, then let AI act on it.*
2. **Per-audience close:**
   - *SAP/App IT:* SAP + non-SAP unified via mirroring/shortcuts/ELT — no
     rip-and-replace; your data stays current and governed.
   - *LOB/Operations:* faster, defensible decisions — the dashboard, the
     real-time alert, and the MPR/award all agree because they share one model.
   - *AI Architects:* a unified, governed semantic layer — the **`EPCOntology`
     (Fabric IQ)** — is the shortcut to **well-grounded** agents: four Foundry
     agents call it natively with **Entra passthrough** (Fabric RBAC per
     request), composed with Web IQ and consumed over the Responses API.
3. **One-line CTA:** *This entire environment is 100% synthetic and
   reproducible — we can stand up the same pattern on your data.*

---

## Pre-demo checklist (presenter)

- [ ] **Data current:** semantic model refreshed / Direct Lake framed; dashboards
      open to Falcon-red state.
- [ ] **Tabs staged:** Fabric Power BI (`EPC Demo` Exec page), `rtdCommissioning`
      Real-Time Dashboard, a mirrored DB item, a OneLake shortcut in bronze, the
      `EPCOntology` (Fabric IQ), the ELT pipeline, and the agent surface
      (Teams/Copilot or web app).
- [ ] **RTI burst:** run `external_sources/rti_commissioning/run_demo_burst.sh`
      (e.g. `./run_demo_burst.sh 300`) ~2 min before Segment 1c so ET-1001 is
      ramping; confirm the Activator email/Teams alert arrives.
- [ ] **Agent smoke test:** ask one MPR and one TBE/CBE prompt (optionally one
      change-notice) beforehand to warm the tools and confirm the Fabric IQ
      grounding resolves.
- [ ] **Fallbacks:** map visual needs the tenant *Map/filled map* setting; if the
      live burst is quiet, the KQL table retains history (`active_alarms()`).

---

## Envisioned additions (build only if we want them on screen)

| Item | Why it strengthens the narrative | Effort |
|---|---|---|
| **`[TO BUILD]` Operations Command page** (Power BI or RTI dashboard tile set) tying ET-1001 telemetry to its PO/permit/work-order/supplier context | Gives Daniel a richer Segment 1c screen; visually closes the real-time↔batch loop | Low–Medium |
| **`[TO BUILD]` Supplier 360 report page** (risk, on-time %, open POs, bid history) | Makes the "same risky supplier" tie-back a *screen*, not just a sentence | Low |
| **`[ENVISIONED]` Foundry IQ tool** — wire the Phase-4 Azure AI Search knowledge corpus into the agents as a second grounding tool | Adds house-style / policy / prior-report grounding alongside the ontology's numbers | Low–Medium |
| **`[ENVISIONED]` Operations agent action** that summarizes an alarming asset's cross-system context on alert | Demonstrates agentic *action* on a real-time trigger in Segment 3e | Medium |

> None of these are required — the core four-segment flow runs entirely on
> what's already built. They're here so we can decide what (if anything) to add
> to sharpen the story.

---

## Timing summary

| Segment | Focus | Time |
|---|---|---|
| 1 | Platform intro + business day-in-the-life (Maya, Daniel) | 10–12 min |
| 2 | Unified data platform / ingestion (native, BigQuery, SQL Server, RTI) | 10–12 min |
| 3 | Agentic AI (EPCOntology / Fabric IQ; four Foundry agents; MPR + bid eval + change notice) | 13–16 min |
| 4 | Wrap-up + per-audience close | 3–4 min |
| | **Total** | **~36–45 min** (+ Q&A) |
