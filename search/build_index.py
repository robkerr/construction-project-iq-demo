#!/usr/bin/env python
"""Phase 4 — build the Azure AI Search 'project-knowledge' index and upload the docs corpus.

Reads the corpus (produced by data_gen/docs_gen.py, published to the Lakehouse by
scripts/32_upload_docs_to_lakehouse.ps1), (re)creates the index defined in search/build_index.md,
and uploads every document with its full markdown body as `content`.

Corpus source (DOCS_SOURCE in .env):
  * onelake (default when FABRIC_WORKSPACE_ID + FABRIC_LAKEHOUSE_ID are set) — read the docs from the
    Lakehouse Files/ section (OneLake DFS API), so the Lakehouse is the canonical store, then *push* to
    the index. (Azure AI Search also has a native OneLake files indexer that could crawl the lakehouse
    automatically; this demo uses push instead — simpler, no managed-identity/workspace-role setup, and
    it keeps the doc_type/project_id facets sourced from corpus_index.json.)
  * local — read the docs straight from the repo docs/ folder.

Auth: DefaultAzureCredential (recommended — assign the identity 'Search Index Data Contributor' +
'Search Service Contributor'; OneLake reads need workspace membership), or set AI_SEARCH_ADMIN_KEY in
.env to use a key for the Search data plane (OneLake reads still use DefaultAzureCredential).

Usage:
    pip install azure-search-documents azure-identity python-dotenv
    python search/build_index.py
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
INDEX_NAME = os.environ.get("AI_SEARCH_INDEX", "project-knowledge")
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"


def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env")
    except Exception:
        pass


def slug(path: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_-]", "-", path.replace("/", "__"))


def _entry_to_doc(entry: dict, body: str) -> dict:
    return {
        "id": slug(entry["path"]),
        "title": entry["title"],
        "doc_type": entry["doc_type"],
        "project_id": entry.get("project_id") or "",
        "path": entry["path"],
        "content": body,
    }


def read_corpus_local() -> list[dict]:
    catalog = json.loads((DOCS / "corpus_index.json").read_text(encoding="utf-8"))
    return [_entry_to_doc(e, (DOCS / e["path"]).read_text(encoding="utf-8")) for e in catalog]


def _onelake_get(base_url: str, rel: str, token: str) -> str:
    url = f"{base_url.rstrip('/')}/{rel.lstrip('/')}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "x-ms-version": "2021-08-06",
    })
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def read_corpus_onelake(credential) -> list[dict]:
    ws = os.environ["FABRIC_WORKSPACE_ID"]
    lh = os.environ["FABRIC_LAKEHOUSE_ID"]
    prefix = os.environ.get("DOCS_ONELAKE_PREFIX", "Files/knowledge").strip("/")
    base = f"{ONELAKE_DFS}/{ws}/{lh}/{prefix}"
    token = credential.get_token("https://storage.azure.com/.default").token
    catalog = json.loads(_onelake_get(base, "corpus_index.json", token))
    print(f"reading corpus from OneLake: {base}/")
    return [_entry_to_doc(e, _onelake_get(base, e["path"], token)) for e in catalog]


def read_corpus(credential) -> list[dict]:
    source = os.environ.get("DOCS_SOURCE")
    if not source:
        source = "onelake" if (os.environ.get("FABRIC_WORKSPACE_ID") and
                               os.environ.get("FABRIC_LAKEHOUSE_ID")) else "local"
    if source.lower() == "onelake":
        return read_corpus_onelake(credential)
    print("reading corpus from local docs/")
    return read_corpus_local()


def build_index(endpoint: str, search_credential, docs) -> None:
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SearchFieldDataType, SimpleField, SearchableField,
        SemanticConfiguration, SemanticField, SemanticPrioritizedFields, SemanticSearch,
    )
    from azure.search.documents import SearchClient

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SimpleField(name="doc_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="project_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="path", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
    ]
    semantic = SemanticSearch(configurations=[
        SemanticConfiguration(
            name="project-knowledge-semantic",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
            ),
        )
    ])
    index = SearchIndex(name=INDEX_NAME, fields=fields, semantic_search=semantic)

    ix_client = SearchIndexClient(endpoint=endpoint, credential=search_credential)
    ix_client.create_or_update_index(index)
    print(f"index '{INDEX_NAME}' created/updated")

    sc = SearchClient(endpoint=endpoint, index_name=INDEX_NAME, credential=search_credential)
    result = sc.upload_documents(documents=docs)
    ok = sum(1 for r in result if r.succeeded)
    print(f"uploaded {ok}/{len(docs)} documents")


def main() -> None:
    load_env()
    endpoint = os.environ.get("AI_SEARCH_ENDPOINT")
    if not endpoint:
        raise SystemExit("Set AI_SEARCH_ENDPOINT in .env (https://<service>.search.windows.net)")

    from azure.identity import DefaultAzureCredential
    aad_credential = DefaultAzureCredential()

    docs = read_corpus(aad_credential)

    admin_key = os.environ.get("AI_SEARCH_ADMIN_KEY")
    if admin_key:
        from azure.core.credentials import AzureKeyCredential
        search_credential = AzureKeyCredential(admin_key)
    else:
        search_credential = aad_credential

    build_index(endpoint, search_credential, docs)


if __name__ == "__main__":
    main()

