# Surfacing in Microsoft 365 Copilot

Expose the agent where project controls managers already work — **M365 Copilot** — as a
**declarative agent**, grounded in the same two sources as the Foundry agent.

## Option A — Declarative agent (Copilot Studio / agent builder)
1. Create a new **declarative agent** named **"Project Controls Assistant"**
   (`M365_DECLARATIVE_AGENT_NAME`).
2. **Instructions:** paste `system_prompt.md`.
3. **Knowledge / capabilities:**
   - **Fabric Data Agent** (structured) — add via its **MCP endpoint**
     (`DATA_AGENT_MCP_ENDPOINT`, ends in `/agent`) so Copilot can query the semantic model.
   - **Azure AI Search** — connect the `project-knowledge` index (`AI_SEARCH_CONNECTION_NAME`) for
     the authoring standard, escalation policy, and prior MPRs.
4. **Conversation starters:**
   - "Which project has the highest schedule risk this month?"
   - "Why is Project Falcon at risk?"
   - "Generate this month's Monthly Progress Report for Project Falcon."
   - "Draft a change notice for the Project Falcon transformer delay."

## Option B — Foundry agent published to Copilot
Publish the Azure AI Foundry agent (built with `system_prompt.md` + the two tools) to Microsoft 365
Copilot / Teams. Same grounding, richer orchestration.

## Demo flow (what to show the client)
1. In M365 Copilot: *"Which project is most at risk and why?"* → **Project Falcon**, with a SAP
   driver **and** a non-SAP driver named — the cross-system insight, in the flow of work.
2. *"Generate this month's MPR for Project Falcon."* → a full report in house style, real numbers,
   Red band, escalation note.
3. *"Draft a change notice for the transformer delay."* → a change notice from the template,
   referencing the same WBS/EC.

## Guardrails
- Read-only against a **synthetic** demo dataset.
- Generic branding throughout (Contoso E&C) — safe to show to any customer.
- The agent must decline questions outside project-controls scope.
