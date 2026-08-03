#!/usr/bin/env python
"""Call an EPC Foundry agent via the Responses API.

This is the reference client for BOTH consumption paths:

  * React app (Entra service principal) — set these env vars and run unchanged:
        AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    DefaultAzureCredential picks them up automatically. The service principal
    needs: `Azure AI User` (or Contributor) on the Foundry project, AND access
    to the Fabric workspace/ontology (the fabric_iq tool uses UserEntraToken
    passthrough, so the *caller's* identity is what hits Fabric).

  * Copilot / CLI session (your user) — just `az login` first; no env vars.

Usage:
  python call_agent.py "Run the technical bid evaluation for RFQ-0001."
  python call_agent.py --agent epc-technical-bid-evaluation "..."
"""
import argparse
import sys

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

import config as C


def ask(agent_name: str, question: str) -> str:
    project = AIProjectClient(endpoint=C.PROJECT_ENDPOINT, credential=DefaultAzureCredential())
    client = project.get_openai_client()

    conversation = client.conversations.create()
    response = client.responses.create(
        conversation=conversation.id,
        input=question,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
    )
    return response.output_text


def main() -> None:
    ap = argparse.ArgumentParser(description="Call an EPC Foundry agent.")
    ap.add_argument("question", nargs="+", help="The question / task for the agent.")
    ap.add_argument("--agent", default="epc-technical-bid-evaluation", help="Agent name.")
    args = ap.parse_args()

    answer = ask(args.agent, " ".join(args.question))
    print(answer)


if __name__ == "__main__":
    sys.exit(main())
