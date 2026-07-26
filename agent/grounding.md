# Phase 6 — Agent: "Project Controls IQ Assistant"

An Azure AI Foundry agent (surfaced in M365 Copilot) that answers portfolio schedule-risk questions
and drafts the **Monthly Progress Report** and **change notices** — grounded in *both* Fabric data
and the document corpus. It never invents numbers; every figure comes from a grounding tool.

## Files
| File | Purpose |
|---|---|
| `grounding.md` | the two grounding sources and when to use each |
| `system_prompt.md` | the agent's instructions / guardrails |
| `m365_copilot.md` | how to surface it as a declarative agent in M365 Copilot |
| `actions/generate_mpr.md` | the Monthly Progress Report action |
| `actions/draft_change_notice.md` | the change-notice action |

## Two grounding sources (this is the architecture)

1. **Structured — Fabric Data Agent** over the *Project Controls IQ* semantic model.
   - Answers "what": scores, drivers, rankings, WBS-level cost/schedule facts.
   - Connected via the Data Agent **MCP endpoint** (`DATA_AGENT_MCP_ENDPOINT`, ends in `/agent`).
   - Returns the fused `Schedule Risk Score` and its SAP + non-SAP drivers.

2. **Unstructured — Azure AI Search** index `project-knowledge` (Phase 4).
   - Answers "how to write it": house style (MPR Authoring Standard), escalation thresholds
     (Schedule-Risk Policy), and prior-MPR exemplars for tone/structure.

The agent **fuses** them: structured numbers + narrative conventions → a report that reads like the
last one and cites real figures. The hero prompt — *"Generate this month's MPR for Project Falcon"* —
exercises both in one turn.

## Model
Use **gpt-4.1** (or gpt-4o). Some regions don't support the Foundry Agent Service Fabric/AI-Search
tools on gpt-5 — see `.env.example` (`FOUNDRY_MODEL`).

## Acceptance
- "Which project is most at risk and why?" → Project Falcon, with **both** a SAP driver (late
  long-lead PO / overrun) and a non-SAP driver (critical-path slip / EC-1207) named.
- "Generate this month's MPR for Project Falcon" → a full MPR following the authoring standard,
  numbers matching the semantic model, Red risk band, escalation per policy.
- Every quantitative claim is traceable to the Data Agent; every stylistic choice to a standard doc.
