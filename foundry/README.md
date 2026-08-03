# Foundry agents (`epc-`)

Azure AI **Foundry** agents for the Construction Project IQ demo, provisioned in the
existing project **`fbcaidemo-dev-project`** alongside the `telco-` agents. All EPC agents
use the `epc-` name prefix and the existing **`gpt-4.1`** model deployment.

## Architecture

Each agent is a **prompt agent** (versioned, server-side) consumed over the **Responses API**
with Microsoft Entra auth. Fabric grounding uses the native **`fabric_iq_preview`** tool pointed
at the **`EPCOntology`** ontology ("Fabric IQ") — the *same* pattern the `telco-` agents use, so:

- **No Fabric data agent** and **no stored secret** — the tool reaches the Fabric ontology MCP
  endpoint through a Foundry project connection with **`UserEntraToken` passthrough**, so the
  **caller's own identity** hits Fabric and Fabric RBAC is enforced per request.
- Optional **`web_search`** tool for general engineering-standard context.

```
Responses API (Entra)                Foundry project: fbcaidemo-dev-project
   caller ──────────────►  epc-technical-bid-evaluation (gpt-4.1)
   (user token or SP)          │  tools:
                               │   ├─ fabric_iq_preview ──(UserEntraToken)──►  Fabric IQ
                               │   │      connection: EPCOntology                EPCOntology
                               │   │      → …/items/<ontology>/ontologyEndpoint  (workspace 8f4cf2c2…)
                               │   └─ web_search
```

## Files

| File | Purpose |
|---|---|
| `config.py` | Shared IDs/endpoints (env-overridable). |
| `agents/epc-technical-bid-evaluation.md` | Instructions for the TBE agent (Priya's scenario). Edit + re-provision to change behavior. |
| `provision_agent.py` | Idempotently ensures the `EPCOntology` connection and creates/updates an agent version. |
| `call_agent.py` | Reference client for **both** consumption paths (user via `az login`, or service principal via env vars). |
| `requirements.txt` | Python deps. |

## Prerequisites

- `az login` as an identity with **Contributor/Owner on the Foundry project** and access to the
  Fabric workspace/ontology.
- The `EPCOntology` ontology item must be reachable (it is, in workspace `8f4cf2c2…`).
- `pip install -r requirements.txt` (into the repo `.venv`).

## Provision / update an agent

```bash
source ../.venv/bin/activate
python provision_agent.py                      # provisions epc-technical-bid-evaluation
# any other epc- agent:
python provision_agent.py --agent epc-xyz --instructions agents/epc-xyz.md
```

Re-running bumps the agent to a new **version** (traffic points at `@latest`).

## Consume the agent

### A. Copilot / CLI session (your user identity)

```bash
az login                                        # once
python call_agent.py "Run the technical bid evaluation for RFQ-0001."
```

`call_agent.py` is the minimal Responses-API pattern; a Copilot CLI session can shell out to it,
or reuse the same three lines (`AIProjectClient` → `get_openai_client()` →
`responses.create(..., extra_body={"agent_reference": {...}})`).

### B. React app via an Entra **service principal**

The same `call_agent.py` works unchanged for a service principal — `DefaultAzureCredential`
reads these env vars:

```bash
export AZURE_TENANT_ID=<tenant>
export AZURE_CLIENT_ID=<sp-app-id>
export AZURE_CLIENT_SECRET=<sp-secret>
python call_agent.py "Evaluate the bids for RFQ-0001 technically."
```

The React frontend calls **your** backend; the backend holds the SP credential and calls the
agent (never expose the SP secret to the browser). The Responses API is OpenAI-compatible, so the
backend can also POST directly to
`{PROJECT_ENDPOINT}/responses?api-version=v1` with a bearer token for `https://ai.azure.com/.default`
and body `{ "input": "...", "agent_reference": { "name": "epc-technical-bid-evaluation", "type": "agent_reference" } }`.

**Service-principal RBAC (required for both Foundry *and* Fabric):**
1. On the Foundry project: grant the SP **`Azure AI User`** (or Contributor).
2. Because grounding uses **`UserEntraToken` passthrough**, the SP identity is what reaches Fabric —
   grant the SP at least **Viewer** on the Fabric workspace `8f4cf2c2…` (and ensure the tenant
   setting *"Service principals can call Fabric public APIs"* is enabled). Without this, the agent
   answers but the `fabric_iq` tool returns nothing.

## Key IDs

| Thing | Value |
|---|---|
| Foundry project endpoint | `https://fbcaidemodevaibeqggrcwh42nu.services.ai.azure.com/api/projects/fbcaidemo-dev-project` |
| Model deployment | `gpt-4.1` (embeddings: `text-embedding-3-large`) |
| Fabric workspace | `8f4cf2c2-381f-4afa-9b7d-9fcfabd4f82d` |
| Ontology item (`EPCOntology`) | `5b14f581-ac41-48db-9d60-a04610e2e9af` |
| Ontology MCP endpoint | `…/v1/mcp/dataPlane/workspaces/8f4cf2c2…/items/5b14f581…/ontologyEndpoint` |
| Project connection | `EPCOntology` (RemoteTool / UserEntraToken, audience `https://api.fabric.microsoft.com`) |

## Agents

| Agent | Persona / scenario | Status |
|---|---|---|
| `epc-technical-bid-evaluation` | **Priya** — Technical Bid Evaluation (TBE) for a tagged-equipment RFQ (hero: RFQ-0001 / ET-1001). | ✅ built |
| `epc-monthly-progress-report` | **Maya** — Monthly Progress Report (MPR) fusing SAP cost/procurement + non-SAP schedule/EC (hero: PRJ-001 Project Falcon). | ✅ built |
| `epc-commercial-bid-evaluation` | **Priya** — Commercial Bid Evaluation (CBE); normalizes quotes to evaluated price, recommends the award (hero: RFQ-0001). Downstream of the TBE. | ✅ built |
| `epc-change-notice` | **Project Controls** — drafts a formal change notice fusing an approved EC and a late long-lead PO on the same WBS (hero: PRJ-001, EC-1207 + transformer PO-00510). | ⚠️ built — see *Known limitation* |

### Known limitation — `epc-change-notice` grounding fidelity

The ontology returns 100% correct data for this agent's tool calls (verified: `PO-00510`,
supplier `Henderson Systems` / `SUP-009`, promised `2026-07-08` → revised `2026-08-02`, `EC-1207`
+18 days on `ACT-000008`, `$1,103,930.67` overrun). However **gpt-4.1 intermittently fabricates the
date-, name-, and short-id-shaped fields** during composition (e.g., renames the supplier, rewrites
the PO dates, or lengthens `PO-00510` to a SAP-style number) — reconstructing them from format
priors instead of copying the tool output. It grounds distinctive dollar amounts reliably (the
CBE/TBE/MPR agents are unaffected because their payload is dollar-figure-heavy). Attempted mitigations
that did **not** fully resolve it: column-style retrieval protocol, `temperature=0`, and a forceful
verbatim-echo rule. **Revisit options:** deploy a stronger model for this agent, or pin the fixed
demo-hero facts into the instructions while keeping the live Fabric IQ call for the grounding story.
