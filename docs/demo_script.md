# Project Controls IQ — Demo Voiceover Script

A **read-aloud narration script** for the demo video. Record the spoken lines as a
voiceover, screen-record the live demo separately, then lay the voice over the
screen capture. It follows the four segments in
[`demo_flow.md`](./demo_flow.md).

### How to use this script
- **Bold `[SCREEN: …]`** lines are *not spoken* — they tell you what to have on
  screen while you read the narration beneath them.
- Plain paragraphs are the **words to speak**. Read at a relaxed pace
  (~140 words/min).
- **`[PAUSE …]`** marks a beat where you stop talking and let the screen do the
  work (a report generating, a dashboard refreshing). Trim the silence later.
- Target durations per segment are guides; the voice is usually shorter than the
  on-screen time because of pauses.

### Pronunciation / say-it-like-this
- **ET-1001** → "E-T ten-oh-one" · **EC-1207** → "E-C twelve-oh-seven"
- **PO-00510** → "P-O oh-five-ten" · **RFQ-0001** → "R-F-Q one"
- **WO-900001** → "work order nine-hundred-thousand-one"
- Spell out on first use: **MPR** = Monthly Progress Report · **TBE** = Technical
  Bid Evaluation · **CBE** = Commercial Bid Evaluation.

### Optional beats (record or skip)
- **Scenario 3 — change notice** (§3d) and the **operations-agent teaser** (§3e)
  are optional. Skip them for the tightest cut; both are marked *OPTIONAL* below.

---

## Cold open — the hero thread *(~0:45)*

**[SCREEN: Title card — "Project Controls IQ on Microsoft Fabric" — or the
Executive Portfolio Overview dashboard, muted.]**

Every large construction program runs on a dozen disconnected systems. Cost lives
in SAP. Schedules live somewhere else. Field equipment reports to a third place.
And the answer you actually need is blends these data sources together.

So here's one story, told four ways. This is **Project Falcon**, a two-hundred-
thirty-kilovolt substation. Its main power transformer — asset **E-T ten-oh-one** —
is late, it's over budget, and during commissioning it starts to overheat. And the
*same* high-risk supplier behind that late transformer is a bidder we
had to disqualify on the replacement.

No single system knows all of that. Microsoft Fabric does — it fuses SAP,
non-SAP, and real-time telemetry into one governed answer, and then lets AI act on
it. Let me show you.

---

# Segment 1 — Fabric as a platform, and a business day-in-the-life
*Target ~10–12 min on screen*

### 1a. The frame

**[SCREEN: One simple architecture slide — OneLake in the center, workloads
around it.]**

The idea behind Fabric is one copy of your data in **OneLake**, with every
workload — data engineering, real-time intelligence, Power BI, and AI agents —
reading the *same* governed data. So everything you're about to see reads one
governed lakehouse — the dashboards through a **semantic model**, the agents
through an **ontology**, both over the same gold tables. No copies, no drift, and
the numbers always reconcile.

### 1b. Maya's morning

**[SCREEN: Power BI → "EPC Demo" workspace → Executive Portfolio Overview.]**

Meet Maya. She's our Project Controls Manager, and this is where her day starts —
the executive portfolio view. A global map of every active project, percent
complete, and a risk read across the whole portfolio. Twelve capital projects at a
glance.

**[SCREEN: Point to Project Falcon showing red; drill into the Portfolio Schedule
Risk page.]**

And one project is red — Project Falcon. When she drills in, the **Schedule Risk
Score** is up around ninety-seven. What makes that number interesting is *where* it
comes from. It's driven by two signals at once: an **SAP** signal — a late
long-lead purchase order and a forecast overrun — *and* a non-SAP signal — an
approved engineering change.

**[SCREEN: Select Project Falcon; point to the "Why Falcon is red" root-cause band
at the bottom of the page.]**

And the dashboard doesn't just hint at it — it *names* the root cause. Down here,
two little tables line up on the **same work package**: engineering change **E-C
twelve-oh-seven**, adding eighteen days on the critical path, sitting right next to
the late long-lead transformer purchase order, **P-O oh-five-ten**. One WBS, two
systems, one collision. That's the whole point.

**[SCREEN: Click "Ask Copilot".]**

But here's the thing — the dashboard tells Maya *what* and *where*. It can't tell
her the *so-what* across the rest of the business. So she asks the agent the
question the dashboard **can't** answer.

**[SCREEN: Type: "What's driving Falcon's schedule risk, and what does the late
transformer PO mean for our sourcing and live field risk?"]**

"What's driving Falcon's schedule risk — and what does that late transformer PO
mean for our sourcing and our live field risk?"

**[PAUSE — let the answer stream in.]**

And the agent makes a leap no dashboard can. That late PO's supplier? It's the same
**high-risk supplier we just disqualified** as the cheapest bidder on the
replacement RFQ. And it's the same transformer — **E-T ten-oh-one** — that Daniel
is about to watch go into alarm, live. No single screen knew all of that. The agent
does, because it reads the **ontology** that ties sourcing, schedule, engineering,
and field telemetry together.

**[SCREEN: Type: "Generate this month's MPR for Falcon."]**

Then: "Generate this month's Monthly Progress Report for Falcon." And out comes a
leadership-ready report, with real numbers. We'll come back to
exactly how that's built — for now, notice she never left her dashboard.

### 1c. Daniel's alert

**[SCREEN: Switch to Teams / email showing the Activator alert.]**

Now, while Maya was talking, something was happening in the field. That same
transformer, E-T ten-oh-one, was being commissioned — and its telemetry was
streaming live into Fabric. Meet Daniel, our commissioning engineer. He just got
an alert: a commissioning asset has entered **alarm**.

**[SCREEN: Open the Real-Time Dashboard "rtdCommissioning" — winding temperature
and hydrogen trends, plus the Active Alarms table.]**

He opens the real-time dashboard. Winding temperature climbing. Dissolved hydrogen
climbing. E-T ten-oh-one is pushing past its commissioning thresholds right now, in
real time.

And here's the tie: this live alarm is reproducing emergency **work order
nine-hundred-thousand-one** — the physical symptom of the very same late, troubled
transformer Maya just flagged from the cost and schedule side. Real-time and batch.
Same asset. Same story.

### 1d. The through-line

**[SCREEN: The ontology diagram (ontology_diagram.png).]**

So how do a finance dashboard and a live equipment feed end up talking about the
 same transformer? Because they resolve to the same business entities —
Project, Work Package, Equipment, Supplier, Purchase Order, Permit, Work Order.

That shared vocabulary is a real, built artifact: the **Fabric IQ ontology**. We
model these entities and their relationships once, over the lakehouse, and then
every dashboard, every query, and every agent speaks the same language. Think of it
as the semantic backbone — and in the next two segments you'll see how it's built,
and how the AI grounds on it.

**[Segment 1 takeaway — you can say this or let it land silently:]**
The headline for Segment 1 is simple: business users already have analytics,
real-time operations, and AI answers — on data that's finally been brought
together for them.

---

# Segment 2 — The unified data platform
*Target ~10–12 min on screen*

### 2a. The picture

**[SCREEN: The base data sources diagram (base_data_sources.png).]**

Let's pull back the curtain on where all that data actually comes from. Four source
systems, plus one live stream, all landing in a single lakehouse.

Fabric-native data holds our core project controls — schedules, engineering
changes, bids — and the permits and inspections. **SAP** brings suppliers,
purchase orders, and cost. **Google BigQuery** brings work-order management.
On-prem **SQL Server** brings the time clock and labor. And an **Eventstream**
brings the live commissioning telemetry.

What's nice is you're looking at four different integration patterns, side by side,
all ending in one place. Let me open each one.

### 2b. Mirroring

**[SCREEN: Open a Mirrored Database item — BigQuery work orders and/or SQL Server.]**

First pattern: **mirroring**. Fabric continuously replicates the source system
into OneLake as Delta — no ETL to build, no nightly extract to babysit, and it's
near-real-time. For our SAP and operational systems, this is how you keep the
analytics layer current *without* a rip-and-replace.

### 2c. Shortcuts

**[SCREEN: Open a OneLake shortcut in the bronze layer pointing at the mirrored
tables.]**

Second pattern: **shortcuts** — zero-copy virtualization. This bronze table isn't a
copy; it's a shortcut that points straight at Delta already sitting in OneLake. The
data never moved, and yet it behaves like a native lakehouse table. One governed
namespace, zero duplication, and everything joins on the same project and equipment
keys.

### 2d. The ELT pipeline

**[SCREEN: Open the pipeline "PL_ELT_Landing_to_Gold" — Copy → notebooks.]**

Third pattern, for when you *do* want a classic orchestrated ingest: a data
pipeline. This one copies raw extracts into a landing folder, then runs notebooks to
build bronze, then silver, then gold. The traditional path is still first-class —
same destination lakehouse, right alongside the zero-copy patterns.

### 2e. Medallion, fusion, and the ontology

**[SCREEN: Show bronze → silver → gold; highlight the gold fusion tables.]**

And here's the payoff of unifying everything. Down in the gold layer we have tables
that could only exist *because* the sources are together — a project schedule-risk
table, a bid-evaluation table, an award recommendation. The work-package key is the
bridge: it's what lets a SAP late-purchase-order line up against a non-SAP schedule
slip on the exact same piece of work — and produce that fused risk score Maya saw.

**[SCREEN: Return to the ontology diagram.]**

Technically, this is also where the **Fabric IQ ontology** lives. Project to work
package to work orders, purchase orders, and engineering changes. Project to bids to
suppliers. Project to permits to inspections. Modeled once over those same gold
tables — the **semantic model** projects them to Power BI, the **ontology** projects
them to the AI agents. Two lenses on one governed layer, which is exactly what makes
those agents well-grounded.

**[Segment 2 takeaway:]**
One lakehouse, many front doors — native, mirror, shortcut, pipeline, and stream.
SAP, BigQuery, SQL Server, and live telemetry all become one governed, queryable
model — read by dashboards through a **semantic model** and by agents through the
**ontology**, two lenses over the same gold layer.

---

# Segment 3 — Agentic AI on the unified layer
*Target ~13–16 min on screen*

### 3a. How the agents are grounded

**[SCREEN: A simple diagram — the four EPC agents, each calling Fabric IQ.]**

Now the part the architects came for. Because the data is unified and governed,
building *well-grounded* agents becomes almost easy.

The source of truth is the ontology — a key component of **Fabric IQ**. It's modeled
over the same gold tables the dashboards' **semantic model** uses, so the agents and
the dashboards can never disagree on a number.

On top of that we developed four purpose-built Azure AI Foundry agents, one per job: a
Monthly Progress Report agent for Maya, a Technical Bid and Commercial Bid Evaluation agents for procurement, and a change-notice agent for
project controls.

And here's the governance detail worth pausing on. Each agent calls a native Fabric
IQ tool that reaches the ontology over a standard M-C-P endpoint — with *no* stored
secret and *no* copy of the data. It passes through the caller's own identity, so
Fabric's own row-level security is enforced per request. Every number the agent
states comes from the ontology; it's not allowed to make one up. There's an optional
web tool for outside context, and the whole thing is consumed over a standard API —
so the same agent shows up in Teams, in Copilot, or in a web app.

### 3b. Scenario 1 — schedule risk to MPR

**[SCREEN: Chat surface. Type: "What's driving Falcon's schedule risk, and what
does the late transformer PO mean for our sourcing and field risk?"]**

Let's put it to work — the same question Maya asked, now let's watch it ground.
"What's driving Falcon's schedule risk — and what does that late transformer PO mean
for our sourcing and field risk?"

**[PAUSE — let the answer stream.]**

And there it is. First it fuses the two sides the dashboard named: the SAP side — the
late long-lead purchase order, **P-O oh-five-ten**, and roughly a
one-point-one-million-dollar overrun — with the non-SAP side, engineering change
**E-C twelve-oh-seven**, both landing on the *same* work package. Then it goes
further than any dashboard can: that PO's supplier is a **high-risk** supplier — and
in a moment we'll see it's the very bidder we disqualify on the replacement RFQ.
Every figure pulled from Fabric IQ.

**[SCREEN: Type: "Generate this month's MPR for Falcon."]**

Now the artifact: "Generate this month's Monthly Progress Report for Falcon."

**[PAUSE — let the report generate.]**

A full report, real numbers, a red risk band, and the escalation. This
is the exact report Maya needed back in Segment 1 — and the agent reads the
**ontology** while the dashboard reads the **semantic model**, both over the same
gold layer, so their numbers match to the cent.

### 3c. Scenario 2 — bid evaluation, technical to commercial

**[SCREEN: Type: "Run the technical bid evaluation for the Falcon transformer,
RFQ-0001."]**

Second scenario — procurement. "Run the technical bid evaluation for the Falcon
transformer, R-F-Q one."

**[PAUSE.]**

This is the Technical Bid Evaluation. It scores every bid for compliance against the
datasheet — and notice what happens: the *cheapest* bidder, who also happens to be a
high-risk supplier, gets **disqualified** on a mandatory requirement.

**[SCREEN: Type: "Now the commercial evaluation — who do we award, and why not the
cheapest?"]**

So then: "Now the commercial evaluation — who do we award, and why not the
cheapest?" The Commercial Bid Evaluation normalizes every quote to a true
*evaluated* price — folding in spares, freight, the cost of schedule delay,
financing, warranty — and recommends the lowest evaluated price among the
*qualified* bidders.

**[SCREEN: Rest on the recommendation.]**

And here's the moment the whole demo has been building to. That disqualified,
cheapest supplier? It's the *same* high-risk supplier whose late transformer is
driving Falcon's schedule risk in Scenario 1 — and whose asset, E-T ten-oh-one,
alarmed live in Segment 1. One supplier, one asset, one project — seen through
cost, schedule, engineering, and telemetry, all at once. No single system could
have told you that. The unified model just did.

### 3d. *OPTIONAL* — Scenario 3, the change notice

**[SCREEN: Type: "Draft the change notice for EC-1207 on Falcon."]**

One more, if you want the paperwork to write itself. "Draft the change notice for
E-C twelve-oh-seven on Falcon."

**[PAUSE.]**

It produces a formal change notice that ties the approved engineering change to that
late long-lead transformer purchase order — on the same work package. It's exactly
the document the risk finding implies, grounded in Fabric IQ, generated in seconds.
Same change, same purchase order, same supplier as before — the ontology keeps every
agent telling one consistent story.

### 3e. *OPTIONAL* — where this goes next

**[SCREEN: The Segment 1 alarm / real-time dashboard.]**

And you can see where this goes next. Take that real-time alarm from Segment 1 and
put an operations agent behind it — one that, the moment E-T ten-oh-one alarms,
summarizes the asset's entire cross-system context — open purchase orders, permits,
work orders, supplier risk — and recommends the next action. Same ontology, same
grounding, now closing the loop in real time.

**[Segment 3 takeaway:]**
Because the data is unified and governed by the ontology, the agents are grounded by
construction — Fabric IQ for the numbers, the web for the world — consumed wherever
people already work.

---

# Segment 4 — Wrap-up
*Target ~3–4 min*

**[SCREEN: Return to the base data sources diagram, or a summary slide.]**

So let's replay the whole thing in one sentence. One late transformer, from one
risky supplier, showed up in cost through SAP, in schedule through non-SAP, in
procurement through the bids, and in the field through real-time telemetry — and
Fabric turned four silos into one answer, then let AI act on it.

Depending on where you sit, here's the takeaway.

If you're in SAP or application IT: your SAP and non-SAP data unify through
mirroring, shortcuts, and pipelines — no rip-and-replace. Your data stays current
and governed.

If you're in the business or operations: you get faster, defensible decisions,
because the dashboard, the real-time alert, and the report all agree — they share
one model.

And if you're an AI architect: a unified, governed semantic layer — the ontology —
is the shortcut to well-grounded agents. Ours call it natively, with the caller's
own identity and Fabric security enforced on every request.

---

### Recording tips
- Record each segment as its own take — it's far easier to re-do one segment than
  the whole thing.
- Leave ~1 second of silence at the start and end of every take for clean edits.
- Where you see **`[PAUSE …]`**, keep talking-silence short in the voice track and
  stretch the *video* clip to cover the agent/report generating.
- If a live agent run is slow or risky on the day, pre-record those screen
  captures and narrate over the recording — the script reads the same either way.
