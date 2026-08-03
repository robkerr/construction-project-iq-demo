"""Shared configuration for the EPC Foundry agents.

Values default to the demo's resources but can be overridden with environment
variables so the same code runs against another project without edits.
"""
import os

# --- Azure AI Foundry project (hosts the agents) ---------------------------------
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID", "7ea90583-182a-46ed-aa37-c4bd96e90887")
RESOURCE_GROUP = os.getenv("FOUNDRY_RESOURCE_GROUP", "rg-fabric-ai-demos")
ACCOUNT_NAME = os.getenv("FOUNDRY_ACCOUNT", "fbcaidemo-dev-ai-beqggrcwh42nu")
PROJECT_NAME = os.getenv("FOUNDRY_PROJECT", "fbcaidemo-dev-project")
PROJECT_ENDPOINT = os.getenv(
    "FOUNDRY_PROJECT_ENDPOINT",
    f"https://{ACCOUNT_NAME.replace('-', '')}.services.ai.azure.com/api/projects/{PROJECT_NAME}",
)
MODEL = os.getenv("FOUNDRY_MODEL", "gpt-4.1")

# All EPC agents share this name prefix inside the project.
AGENT_PREFIX = os.getenv("EPC_AGENT_PREFIX", "epc-")

# --- Fabric IQ (ontology) grounding source ---------------------------------------
# The EPC ontology ("Fabric IQ") the agents ground on. The MCP ontology endpoint is
# reached through a Foundry project connection using UserEntraToken passthrough, so
# no secret is stored and Fabric RBAC is enforced per caller.
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID", "8f4cf2c2-381f-4afa-9b7d-9fcfabd4f82d")
ONTOLOGY_ITEM_ID = os.getenv("FABRIC_ONTOLOGY_ITEM_ID", "5b14f581-ac41-48db-9d60-a04610e2e9af")
ONTOLOGY_CONNECTION_NAME = os.getenv("FABRIC_ONTOLOGY_CONNECTION", "EPCOntology")
FABRIC_AUDIENCE = "https://api.fabric.microsoft.com"

ONTOLOGY_ENDPOINT = (
    f"{FABRIC_AUDIENCE}/v1/mcp/dataPlane/workspaces/{FABRIC_WORKSPACE_ID}"
    f"/items/{ONTOLOGY_ITEM_ID}/ontologyEndpoint"
)

# Full ARM resource id of the project connection (what the agent tool references).
ONTOLOGY_CONNECTION_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.CognitiveServices/accounts/{ACCOUNT_NAME}"
    f"/projects/{PROJECT_NAME}/connections/{ONTOLOGY_CONNECTION_NAME}"
)
