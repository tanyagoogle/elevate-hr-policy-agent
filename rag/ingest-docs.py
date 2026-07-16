#!/usr/bin/env python3
"""Import documents from GCS into the Vertex AI Search data store (Track A / RAG).

Reads configuration from environment variables (or --flags):
    GOOGLE_CLOUD_PROJECT        GCP project id
    VERTEX_AI_SEARCH_LOCATION   data store location (default: global)
    VERTEX_AI_DATA_STORE_ID     data store id (default: hr-policies-lab-store)

Usage:
    uv run python rag/ingest-docs.py \
        --project "$GOOGLE_CLOUD_PROJECT" \
        --gcs-uri "gs://${GOOGLE_CLOUD_PROJECT}-hr-policies-source/*"

Prerequisites:
    uv sync (installs google-cloud-discoveryengine)
    gcloud auth application-default login
    # and the bucket/data store created via rag/vertex-search-setup.tf
"""
import argparse
import os
import sys
import time

try:
    from google.cloud import discoveryengine_v1
except ImportError:
    print("[ERROR] uv sync (installs google-cloud-discoveryengine)")
    sys.exit(2)


def main():
    parser = argparse.ArgumentParser(description="Ingest handbook docs into Vertex AI Search")
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--location", default=os.getenv("VERTEX_AI_SEARCH_LOCATION", "global"))
    parser.add_argument("--data-store-id", default=os.getenv("VERTEX_AI_DATA_STORE_ID", "hr-policies-lab-store"))
    parser.add_argument("--gcs-uri", help="e.g. gs://<project>-hr-policies-source/*")
    args = parser.parse_args()

    if not args.project:
        print("[ERROR] --project or GOOGLE_CLOUD_PROJECT is required.")
        sys.exit(1)
    gcs_uri = args.gcs_uri or f"gs://{args.project}-hr-policies-source/*"

    client = discoveryengine_v1.DocumentServiceClient()
    parent = (
        f"projects/{args.project}/locations/{args.location}"
        f"/collections/default_collection/dataStores/{args.data_store_id}/branches/0"
    )

    request = discoveryengine_v1.ImportDocumentsRequest(
        parent=parent,
        gcs_source=discoveryengine_v1.GcsSource(input_uris=[gcs_uri], data_schema="content"),
        # Full reconciliation so re-runs replace prior state.
        reconciliation_mode=discoveryengine_v1.ImportDocumentsRequest.ReconciliationMode.FULL,
    )

    print(f"Importing {gcs_uri} -> {parent} ...")
    operation = client.import_documents(request=request)
    print(f"Operation: {operation.operation.name}")

    while not operation.done():
        print("  ... indexing (this can take several minutes)")
        time.sleep(15)

    if operation.exception():
        print(f"[FAILED] {operation.exception()}")
        sys.exit(1)
    print("[DONE] Import finished. Verify with: uv run python rag/verify-rag-search.py --query '...'")


if __name__ == "__main__":
    main()
