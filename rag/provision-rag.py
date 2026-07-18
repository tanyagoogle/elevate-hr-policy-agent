#!/usr/bin/env python3
"""Provision or destroy Track A (Vertex AI Search / GCS) infrastructure without Terraform.

Usage:
    # 1. Provision GCS bucket, upload handbook.pdf, and create Vertex AI Search engine:
    uv run python rag/provision-rag.py --project "$GOOGLE_CLOUD_PROJECT"

    # 2. Clean up / delete resources after the lab:
    uv run python rag/provision-rag.py --project "$GOOGLE_CLOUD_PROJECT" --destroy
"""
import argparse
import os
import sys
import time

try:
    from google.cloud import discoveryengine_v1
    from google.cloud import storage
    from google.api_core.exceptions import AlreadyExists, NotFound
except ImportError:
    print("[ERROR] Missing required libraries. Run: uv sync")
    sys.exit(2)


def get_project_number(project_id: str) -> str:
    """Retrieve the GCP project number via Resource Manager API or gcloud fallback."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return ""


def provision(project_id: str, region: str, location: str, data_store_id: str, engine_id: str):
    bucket_name = f"{project_id}-hr-policies-source"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_path = os.path.join(repo_root, "data", "handbook.pdf")

    print(f"[1/4] Setting up GCS bucket: gs://{bucket_name} ...")
    storage_client = storage.Client(project=project_id)
    try:
        bucket = storage_client.get_bucket(bucket_name)
        print(f"  ✓ Bucket gs://{bucket_name} already exists.")
    except NotFound:
        bucket = storage_client.create_bucket(bucket_name, location=region)
        print(f"  ✓ Created bucket gs://{bucket_name} in {region}.")

    print(f"[2/4] Uploading {pdf_path} -> gs://{bucket_name}/handbook.pdf ...")
    blob = bucket.blob("handbook.pdf")
    if not blob.exists():
        blob.upload_from_filename(pdf_path, content_type="application/pdf")
        print("  ✓ Uploaded handbook.pdf.")
    else:
        print("  ✓ handbook.pdf already present in bucket.")

    # Grant Discovery Engine Service Account access to the bucket
    proj_num = get_project_number(project_id)
    if proj_num:
        sa_email = f"service-{proj_num}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
        print(f"  ✓ Ensuring Discovery Engine SA ({sa_email}) has storage.objectViewer on bucket ...")
        policy = bucket.get_iam_policy(requested_policy_version=3)
        policy.bindings.append({"role": "roles/storage.objectViewer", "members": {f"serviceAccount:{sa_email}"}})
        try:
            bucket.set_iam_policy(policy)
        except Exception as e:
            print(f"  (Note: IAM update skipped/tolerated: {e})")

    print(f"[3/4] Creating Vertex AI Search Data Store: {data_store_id} ({location}) ...")
    ds_client = discoveryengine_v1.DataStoreServiceClient()
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection"
    
    data_store = discoveryengine_v1.DataStore(
        display_name="HR Policy Lab Data Store",
        industry_vertical=discoveryengine_v1.DataStore.IndustryVertical.GENERIC,
        solution_types=[discoveryengine_v1.DataStore.SolutionType.SOLUTION_TYPE_SEARCH],
        content_config=discoveryengine_v1.DataStore.ContentConfig.CONTENT_REQUIRED,
    )
    try:
        op = ds_client.create_data_store(
            parent=parent,
            data_store=data_store,
            data_store_id=data_store_id,
        )
        print("  ... waiting for data store creation ...")
        op.result()
        print(f"  ✓ Data store {data_store_id} created.")
    except AlreadyExists:
        print(f"  ✓ Data store {data_store_id} already exists.")

    print(f"[4/4] Creating Vertex AI Search Engine: {engine_id} ({location}) ...")
    engine_client = discoveryengine_v1.EngineServiceClient()
    engine = discoveryengine_v1.Engine(
        display_name="HR Policy Lab Search",
        solution_type=discoveryengine_v1.SolutionType.SOLUTION_TYPE_SEARCH,
        data_store_ids=[data_store_id],
        search_engine_config=discoveryengine_v1.Engine.SearchEngineConfig(
            search_tier=discoveryengine_v1.SearchTier.SEARCH_TIER_ENTERPRISE,
        ),
    )
    try:
        op = engine_client.create_engine(
            parent=parent,
            engine=engine,
            engine_id=engine_id,
        )
        print("  ... waiting for search engine creation ...")
        op.result()
        print(f"  ✓ Search engine {engine_id} created.")
    except AlreadyExists:
        print(f"  ✓ Search engine {engine_id} already exists.")

    print("\n[DONE] Infrastructure ready!")
    print(f"Next step -> Ingest documents: uv run python rag/ingest-docs.py --project {project_id}")


def destroy(project_id: str, region: str, location: str, data_store_id: str, engine_id: str):
    print(f"Cleaning up Vertex AI Search & GCS resources for project {project_id} ...")
    parent = f"projects/{project_id}/locations/{location}/collections/default_collection"

    engine_client = discoveryengine_v1.EngineServiceClient()
    engine_name = f"{parent}/engines/{engine_id}"
    try:
        print(f"Deleting Search Engine: {engine_id} ...")
        op = engine_client.delete_engine(name=engine_name)
        op.result()
        print("  ✓ Search engine deleted.")
    except Exception as e:
        print(f"  (Search engine delete skipped: {e})")

    ds_client = discoveryengine_v1.DataStoreServiceClient()
    ds_name = f"{parent}/dataStores/{data_store_id}"
    try:
        print(f"Deleting Data Store: {data_store_id} ...")
        op = ds_client.delete_data_store(name=ds_name)
        op.result()
        print("  ✓ Data store deleted.")
    except Exception as e:
        print(f"  (Data store delete skipped: {e})")

    bucket_name = f"{project_id}-hr-policies-source"
    storage_client = storage.Client(project=project_id)
    try:
        print(f"Deleting GCS Bucket: gs://{bucket_name} ...")
        bucket = storage_client.get_bucket(bucket_name)
        bucket.delete(force=True)
        print("  ✓ Bucket deleted.")
    except Exception as e:
        print(f"  (Bucket delete skipped: {e})")

    print("\n[DONE] Cleanup complete.")


def main():
    parser = argparse.ArgumentParser(description="Provision or Destroy Vertex AI Search Track A resources")
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--region", default="asia-southeast1")
    parser.add_argument("--location", default=os.getenv("VERTEX_AI_SEARCH_LOCATION", "global"))
    parser.add_argument("--data-store-id", default=os.getenv("VERTEX_AI_DATA_STORE_ID", "hr-policies-lab-store"))
    parser.add_argument("--engine-id", default=os.getenv("VERTEX_AI_SEARCH_ENGINE_ID", "hr-policies-lab-engine"))
    parser.add_argument("--destroy", action="store_true", help="Destroy resources instead of provisioning")
    args = parser.parse_args()

    if not args.project:
        print("[ERROR] --project or GOOGLE_CLOUD_PROJECT environment variable is required.")
        sys.exit(1)

    if args.destroy:
        destroy(args.project, args.region, args.location, args.data_store_id, args.engine_id)
    else:
        provision(args.project, args.region, args.location, args.data_store_id, args.engine_id)


if __name__ == "__main__":
    main()
