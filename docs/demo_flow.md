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
to overheat. The **same high-risk supplier** whose late PO (**PO-00512**) drives
Falcon's schedule risk is the **cheapest bidder we disqualified** on the
transformer RFQ. No single system knows this. **Fabric fuses SAP + non-SAP +
real-time telemetry into one governed answer**, and the AI agents act on it.

| Where it shows up | Segment |
|---|---|
| Falcon is the #1 portfolio risk (dashboard + agent writes the MPR) | 1 & 3 |
| ET-1001 telemetry ramps to **alarm** live; ops gets notified | 1 |
| The data came from BigQuery, SQL Server, S3, Eventstream — unified in OneLake | 2 |
| Cheapest transformer bid ≠ best value; disqualified supplier = the late-PO supplier | 3 |

---

## Audience map (make sure each person gets "their moment")

| Audience | What they came for | Where they lean in |
|---|---|---|
| **SAP / Application IT** | How SAP + non-SAP data unify without rip-and-replace | Seg 2 (mirroring, shortcuts, ELT), Seg 3 (grounded answers over SAP data) |
| **LOB / Operations** | Faster, better decisions; day-in-the-life | Seg 1 (dashboards, RTI alert, Copilot), Seg 3 (MPR / bid award) |
| **AI Architects / thought leaders** | How to build *well-grounded* agents | Seg 2 (unified layer + ontology), Seg 3 (Data Agents, MCP, Fabric/Foundry/Web IQ) |

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
  workload (Data Engineering, Real-Time Intelligence, Power BI, Data Agents)
  reading the *same* governed model. "Everything you're about to see reads one
  lakehouse and one semantic model."

### 1b. Maya's morning — portfolio decision (4 min)
1. Open **Power BI in Fabric → `EPCDemo` → Executive Portfolio Overview**.
   - Global **project map** (lat/lon), portfolio KPI cards (Active Projects,
     Avg % Complete), %-complete and risk bars. Twelve capital projects.
2. **Project Falcon is red.** Drill to **Portfolio Schedule Risk** page — the
   **Schedule Risk Score** (~96) is driven by **both** a SAP signal (late
   long-lead PO + forecast overrun) and a non-SAP signal (approved engineering
   change **EC-1207**, negative critical-path float).
3. Spot-the-issue → **"⚠ Ask Copilot."** Maya opens the agent (previewed here,
   deep-dived in Segment 3): *"Why is Falcon the top risk this month?"* → a
   grounded, cited answer that spans both systems. *"Generate this month's MPR
   for Falcon."* → a house-style report with real numbers.

> **Why it lands:** the fused **Schedule Risk Score** is the payoff of the
> unified layer — foreshadow that Segment 2 shows *where those signals live*.

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

### 1d. The through-line: one semantic layer / ontology (1–2 min)
- Both Maya's dashboard and Daniel's real-time view resolve to the **same
  business entities** — Project, Work Package, **Equipment/Asset (ET-1001)**,
  Supplier, PO, Permit, Work Order.
- **`[ENVISIONED]` Fabric ontology / Digital Twin Builder** over the lakehouse
  `silver`/`gold` tables + the RTI KQL stream: model those entities and their
  relationships once, so every dashboard, agent, and query speaks the same
  language. Preview it here as the "semantic backbone," then show how it's built
  in Segment 2. (See *Envisioned additions* below.)

**Segment 1 takeaway:** *Business users already get analytics, real-time
operations, and AI answers — on data that's been brought together for them.*

---

# Segment 2 — The unified data platform (where the data comes from)
*~10–12 min · audience: SAP/Application IT-forward, Architects*

**Goal:** Put a concrete, visual picture around the "unified data layer"
marketing. Show the **five ingestion patterns** feeding one bronze/silver/gold
lakehouse — *where* each source lives and *how* it's wired, at a high level. You
won't configure anything live; you'll open the finished config and narrate it.

### 2a. The unified-layer picture (2 min)
Draw/return to a single diagram: **five sources → OneLake bronze → silver →
gold → one semantic model → dashboards + agents.**

| # | Source system | Subject | Into Fabric via |
|---|---|---|---|
| 1 | Google **BigQuery** | Work-order management | **Mirroring** → shortcut in bronze |
| 2 | On-prem **SQL Server** | Time clock / labor | **Mirroring** → shortcut in bronze |
| 3 | Amazon **S3** (Delta) | Government permits & inspections | **Shortcut** (zero-copy) into bronze |
| 4 | Amazon **S3** (raw Parquet) | Core project / SAP landing data | **ELT pipeline** → `Files/landing` → notebooks |
| 5 | **Eventstream** (custom app) | Equipment commissioning telemetry (IIoT) | **RTI** → KQL Database (Eventhouse) |

Four headline patterns side by side: **mirroring** (near-real-time replication),
**shortcuts** (zero-copy virtualization), **ELT pipeline** (Copy + notebook
orchestration), and **RTI** (event stream → KQL).

### 2b. Mirroring — SAP-adjacent and operational systems (3 min)
- Open a **mirrored database** item (BigQuery work orders and/or SQL Server time
  clock). Narrate: Fabric **replicates** the source continuously into OneLake as
  Delta — no ETL to maintain, near-real-time, and it lands as a **shortcut in
  bronze** so it's queryable next to everything else.
- **SAP angle:** this is the pattern for keeping SAP/operational data current in
  the analytics layer *without* rip-and-replace or brittle nightly extracts.

### 2c. Shortcuts — zero-copy virtualization (2 min)
- Open the **S3 Delta shortcut** (government permits/inspections) in bronze.
  Narrate: **the data never moved** — Fabric points at the S3 Delta tables and
  they behave like native lakehouse tables. One credential, zero copies, instant
  fusion on `project_id` / `equipment_tag`.

### 2d. ELT pipeline — the traditional path, still first-class (2 min)
- Open **`PL_ELT_Landing_to_Gold`**: Copy S3 raw Parquet → `Files/landing` →
  run notebooks `02_load_bronze` → `03_build_silver_gold`. Narrate: when you
  *do* want a classic, orchestrated ingest, it's right here alongside the
  zero-copy patterns — same destination lakehouse.

### 2e. Medallion + the fused answer (2 min)
- Show `bronze → silver → gold`. Call out the **fusion tables** that only exist
  because the sources are unified:
  `gold.project_schedule_risk`, `gold.bid_evaluation`,
  `gold.rfq_award_recommendation` (plus `at_risk_activities`, `late_procurement`).
- **`dim_wbs` is the SAP ↔ non-SAP bridge** — the work-package key that lets the
  **Schedule Risk Score** combine a SAP late-PO/overrun with a non-SAP
  change/float slip on the *same* work package.
- **`[ENVISIONED]` ontology** lands here technically: build a Fabric ontology /
  Digital Twin Builder over `silver`/`gold` + RTI so the entities and
  relationships are modeled once and reused by Power BI, Data Agents, and
  operations agents. This is the "unified **semantic** layer" that makes
  Segment 3's agents well-grounded.

**Segment 2 takeaway:** *One lakehouse, many front doors (mirror, shortcut,
pipeline, stream). BigQuery, SQL Server, S3, and IIoT all become one governed,
queryable model — with an ontology as the shared vocabulary.*

---

# Segment 3 — Agentic AI on the unified data layer
*~12–15 min · audience: AI Architects-forward, LOB for the payoff*

**Goal:** Show that the unified/governed layer is exactly what makes
**well-grounded** agents easy to build — and demonstrate the two AI scenarios
that *also* produced two of the Power BI reports.

### 3a. How the agents are grounded (3 min — architecture)
- **Fabric Data Agent** over the **`ProjectControlsIQ`** Direct Lake semantic
  model → exposes an **MCP endpoint** (`.../agent`). The agent answers with the
  *same measures* the dashboards use (Schedule Risk Score, Risk Band, TBE/CBE),
  so numbers never disagree.
- **Azure AI Foundry agent** (`gpt-4.1`) composed of tools:
  - **Fabric IQ** — the Data Agent / MCP endpoint over the governed model
    (structured, numeric truth).
  - **Foundry IQ** — Azure AI Search over the **knowledge corpus** (standards,
    escalation policy, prior MPRs, TBE/CBE standards, supplier quotations).
  - **Web IQ** — public/web grounding for anything outside the four walls.
  - Four **actions**: `generate_mpr`, `draft_change_notice`, `generate_tbe`,
    `generate_cbe`.
- **`[NEW]` MCP endpoints in Foundry** — call out that wiring a Fabric Data
  Agent into Foundry via **MCP** is the new, standards-based way to give an agent
  governed enterprise data as a tool. Walk the config at a high level.
- Publish path: **M365 Copilot / Teams** declarative agent so business users
  consume it where they already work.

### 3b. AI Scenario 1 — Portfolio schedule risk → MPR (4 min)
*(This scenario also produced the **Portfolio Schedule Risk** report.)*
1. In **Teams/Copilot**: *"Why is Project Falcon the top schedule risk?"* →
   grounded answer fusing SAP (late PO-00512, ~$1M overrun) + non-SAP (EC-1207,
   negative float), with citations from Search.
2. *"Generate this month's MPR for Falcon."* → full report in house style, real
   numbers — the artifact Maya needed in Segment 1.
3. Point back: *the agent and the dashboard read the same model.*

### 3c. AI Scenario 2 — Bid evaluation TBE → CBE (5 min)
*(This scenario also produced the **Bid Evaluation** report.)*
1. *"Run the technical bid evaluation for the Falcon transformer (RFQ-0001)."* →
   **TBE**: weighted compliance vs the datasheet; the **cheapest** bidder (a
   **high-risk** supplier) is **disqualified** on a mandatory requirement.
2. *"Now the commercial evaluation — who do we award, and why not the cheapest?"*
   → **CBE**: quotes normalized to an **evaluated price** (spares, freight,
   schedule-delay, financing, warranty loadings); award goes to the lowest
   *evaluated* price among *qualified* bidders.
3. **Payoff tie-back:** the disqualified cheapest supplier is the **same
   high-risk supplier** whose late transformer PO drives Falcon's schedule risk
   in Scenario 1 — and whose asset (ET-1001) alarmed in Segment 1. One supplier,
   one asset, one project — seen by cost, schedule, engineering, and telemetry
   at once.

### 3d. `[ENVISIONED]` Operations agent closing the real-time loop (1–2 min)
- Frame the Segment 1 Activator alert as an **operations agent** pattern: a
  real-time trigger (ET-1001 alarm) that can **notify, summarize the asset's
  cross-system context** (open PO, permits, work order, supplier risk) via the
  same MCP/ontology grounding, and recommend the next action. Show the alert; if
  we build the summarizer action, demo it here.

**Segment 3 takeaway:** *Because the data is unified and governed, agents are
grounded by construction — Fabric IQ for the numbers, Foundry IQ for the
documents, Web IQ for the world — and consumed in Teams/Copilot.*

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
   - *AI Architects:* a unified, governed semantic layer (+ ontology) is the
     shortcut to **well-grounded** agents — Data Agents, MCP endpoints, and the
     Fabric/Foundry/Web IQ composition.
3. **One-line CTA:** *This entire environment is 100% synthetic and
   reproducible — we can stand up the same pattern on your data.*

---

## Pre-demo checklist (presenter)

- [ ] **Data current:** semantic model refreshed / Direct Lake framed; dashboards
      open to Falcon-red state.
- [ ] **Tabs staged:** Fabric Power BI (`EPCDemo` Exec page), `rtdCommissioning`
      Real-Time Dashboard, a mirrored DB item, an S3 shortcut, the ELT pipeline,
      Teams/Copilot with the agent.
- [ ] **RTI burst:** run `external_sources/rti_commissioning/run_demo_burst.sh`
      (e.g. `./run_demo_burst.sh 300`) ~2 min before Segment 1c so ET-1001 is
      ramping; confirm the Activator email/Teams alert arrives.
- [ ] **Agent smoke test:** ask one MPR and one TBE/CBE prompt beforehand to warm
      the tools and confirm citations resolve.
- [ ] **Fallbacks:** map visual needs the tenant *Map/filled map* setting; if the
      live burst is quiet, the KQL table retains history (`active_alarms()`).

---

## Envisioned additions (build only if we want them on screen)

| Item | Why it strengthens the narrative | Effort |
|---|---|---|
| **`[ENVISIONED]` Fabric ontology / Digital Twin Builder** over `silver`/`gold` + RTI | Makes the "unified **semantic** layer" concrete; single vocabulary for dashboards + agents; strong Architect payoff | Medium |
| **`[TO BUILD]` Operations Command page** (Power BI or RTI dashboard tile set) tying ET-1001 telemetry to its PO/permit/work-order/supplier context | Gives Daniel a richer Segment 1c screen; visually closes the real-time↔batch loop | Low–Medium |
| **`[TO BUILD]` Supplier 360 report page** (risk, on-time %, open POs, bid history) | Makes the "same risky supplier" tie-back a *screen*, not just a sentence | Low |
| **`[ENVISIONED]` Operations agent action** that summarizes an alarming asset's cross-system context on alert | Demonstrates agentic *action* on a real-time trigger in Segment 3d | Medium |

> None of these are required — the core four-segment flow runs entirely on
> what's already built. They're here so we can decide what (if anything) to add
> to sharpen the story.

---

## Timing summary

| Segment | Focus | Time |
|---|---|---|
| 1 | Platform intro + business day-in-the-life (Maya, Daniel) | 10–12 min |
| 2 | Unified data platform / ingestion (BigQuery, SQL Server, S3, RTI) | 10–12 min |
| 3 | Agentic AI (Data Agents, MCP, Fabric/Foundry/Web IQ; MPR + bid eval) | 12–15 min |
| 4 | Wrap-up + per-audience close | 3–4 min |
| | **Total** | **~35–43 min** (+ Q&A) |
