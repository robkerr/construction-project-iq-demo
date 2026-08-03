#!/usr/bin/env python
"""Provision an EPC agent in the Foundry project `fbcaidemo-dev-project`.

What it does (idempotent):
  1. Ensures the `EPCOntology` project connection exists (RemoteTool /
     UserEntraToken passthrough to the Fabric IQ ontology MCP endpoint).
  2. Creates or updates a versioned **prompt** agent (`epc-...`) grounded on that
     ontology via the native `fabric_iq_preview` tool, plus optional web search.

Auth: uses your `az login` identity (DefaultAzureCredential). The signed-in
identity needs Contributor/Owner on the Foundry project and access to the Fabric
workspace/ontology.

Usage:
  python provision_agent.py                       # provisions the TBE agent
  python provision_agent.py --agent epc-xyz \
      --instructions agents/epc-xyz.md --no-web    # any other epc- agent
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    FabricIQPreviewTool,
    WebSearchTool,
)

import config as C

HERE = Path(__file__).parent


def ensure_ontology_connection() -> None:
    """Create/update the Fabric IQ ontology connection via ARM (idempotent).

    Requires the Azure CLI. If `az` is unavailable, we skip and assume the
    connection already exists (the agent create step will fail clearly if not).
    """
    body = {
        "properties": {
            "category": "RemoteTool",
            "target": C.ONTOLOGY_ENDPOINT,
            "authType": "UserEntraToken",
            "audience": C.FABRIC_AUDIENCE,
            "group": "GenericProtocol",
            "isSharedToAll": False,
            "metadata": {"type": "fabric_iq_preview"},
            "useWorkspaceManagedIdentity": False,
        }
    }
    url = (
        f"https://management.azure.com{C.ONTOLOGY_CONNECTION_ID}"
        f"?api-version=2025-04-01-preview"
    )
    try:
        subprocess.run(
            ["az", "rest", "--method", "PUT", "--url", url, "--body", json.dumps(body)],
            check=True, capture_output=True, text=True,
        )
        print(f"[connection] ensured '{C.ONTOLOGY_CONNECTION_NAME}' -> ontology endpoint")
    except FileNotFoundError:
        print("[connection] az CLI not found; assuming connection already exists", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"[connection] WARNING: could not ensure connection: {e.stderr}", file=sys.stderr)


def build_tools(with_web: bool):
    tools = [
        FabricIQPreviewTool(
            project_connection_id=C.ONTOLOGY_CONNECTION_ID,
            server_label="EPCOntology",
            server_url=C.ONTOLOGY_ENDPOINT,
            require_approval="never",
        )
    ]
    if with_web:
        tools.append(WebSearchTool())
    return tools


def create_or_update_agent(name: str, instructions_path: Path, with_web: bool, temperature: float) -> None:
    instructions = instructions_path.read_text(encoding="utf-8")
    client = AIProjectClient(endpoint=C.PROJECT_ENDPOINT, credential=DefaultAzureCredential())

    definition = PromptAgentDefinition(
        model=C.MODEL,
        instructions=instructions,
        tools=build_tools(with_web),
        temperature=temperature,
    )
    version = client.agents.create_version(agent_name=name, definition=definition)
    print(f"[agent] '{name}' version {version.version} created/updated (model {C.MODEL}, temperature {temperature}).")
    print(f"[agent] tools: fabric_iq_preview(EPCOntology){' + web_search' if with_web else ''}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Provision an EPC Foundry agent.")
    ap.add_argument("--agent", default="epc-technical-bid-evaluation", help="Agent name (epc- prefix).")
    ap.add_argument("--instructions", default=None, help="Path to the instructions markdown file.")
    ap.add_argument("--no-web", dest="web", action="store_false", help="Do not attach the web_search tool.")
    ap.add_argument("--skip-connection", action="store_true", help="Skip ensuring the ontology connection.")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="Sampling temperature (default 0 for faithful, grounded output).")
    ap.set_defaults(web=True)
    args = ap.parse_args()

    instructions_path = Path(args.instructions) if args.instructions else HERE / "agents" / f"{args.agent}.md"
    if not instructions_path.exists():
        sys.exit(f"Instructions file not found: {instructions_path}")

    if not args.skip_connection:
        ensure_ontology_connection()
    create_or_update_agent(args.agent, instructions_path, args.web, args.temperature)


if __name__ == "__main__":
    main()
