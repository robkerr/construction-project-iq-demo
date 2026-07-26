#!/usr/bin/env python
"""Phase 4 — build the Azure AI Search 'project-knowledge' index and upload the docs corpus.

Reads docs/corpus_index.json (produced by data_gen/docs_gen.py), (re)creates the index defined in
search/build_index.md, and uploads every document with its full markdown body as `content`.

Auth: DefaultAzureCredential (recommended — assign the identity 'Search Index Data Contributor' +
'Search Service Contributor'), or set AI_SEARCH_ADMIN_KEY in .env to use a key.

Usage:
    pip install azure-search-documents azure-identity python-dotenv
    python search/build_index.py
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
INDEX_NAME = os.environ.get("AI_SEARCH_INDEX", "project-knowledge")


def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO / ".env")
    except Exception:
        pass


def slug(path: str) -> str:
    return re.sub(r"[^0-9a-zA-Z_-]", "-", path.replace("/", "__"))


def read_corpus() -> list[dict]:
    catalog = json.loads((DOCS / "corpus_index.json").read_text(encoding="utf-8"))
    docs = []
    for entry in catalog:
        body = (DOCS / entry["path"]).read_text(encoding="utf-8")
        docs.append({
            "id": slug(entry["path"]),
            "title": entry["title"],
            "doc_type": entry["doc_type"],
            "project_id": entry.get("project_id") or "",
            "path": entry["path"],
            "content": body,
        })
    return docs


def build_index(endpoint: str, credential) -> None:
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SearchField, SearchFieldDataType, SimpleField, SearchableField,
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

    ix_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    ix_client.create_or_update_index(index)
    print(f"index '{INDEX_NAME}' created/updated")

    docs = read_corpus()
    sc = SearchClient(endpoint=endpoint, index_name=INDEX_NAME, credential=credential)
    result = sc.upload_documents(documents=docs)
    ok = sum(1 for r in result if r.succeeded)
    print(f"uploaded {ok}/{len(docs)} documents")


def main() -> None:
    load_env()
    endpoint = os.environ.get("AI_SEARCH_ENDPOINT")
    if not endpoint:
        raise SystemExit("Set AI_SEARCH_ENDPOINT in .env (https://<service>.search.windows.net)")

    admin_key = os.environ.get("AI_SEARCH_ADMIN_KEY")
    if admin_key:
        from azure.core.credentials import AzureKeyCredential
        credential = AzureKeyCredential(admin_key)
    else:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()

    build_index(endpoint, credential)


if __name__ == "__main__":
    main()
