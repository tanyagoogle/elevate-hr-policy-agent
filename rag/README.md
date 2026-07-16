# Track A — Vertex AI Search (RAG) setup

This provisions the RAG "brain": a Vertex AI Search data store built from the
handbook PDF. Your agent's `search_policy_docs` tool queries it.

> 💸 **Cost:** Vertex AI Search is a billable, enterprise-tier service. **Run
> `terraform destroy` when you finish the lab** (last step below).

## Prerequisites

- A GCP project with billing enabled, and the Discovery Engine API enabled:
  ```bash
  gcloud services enable discoveryengine.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"
  gcloud auth application-default login
  ```
- Terraform ≥ 1.5 (Python deps are installed by `uv sync`).
- Set `GOOGLE_CLOUD_PROJECT`, `VERTEX_AI_DATA_STORE_ID`, `VERTEX_AI_SEARCH_ENGINE_ID`
  in your `.env` (defaults match the Terraform defaults).

## 1. Provision the bucket + data store + engine

```bash
cd rag
terraform init
terraform apply -var="project_id=$GOOGLE_CLOUD_PROJECT"
```

Terraform uploads `../data/handbook.pdf` to the source bucket automatically.

## 2. Ingest / index the documents

```bash
cd ..
uv run python rag/ingest-docs.py --project "$GOOGLE_CLOUD_PROJECT"
```

Indexing can take several minutes. Re-running re-indexes (full reconciliation).

## 3. Verify retrieval

```bash
uv run python rag/verify-rag-search.py --query "outpatient sick leave and medical certificate"
# no cloud yet? try the offline mock:
uv run python rag/verify-rag-search.py --mock --query "sick leave"
```

You should see titles + citation links. Once this looks right, implement
`agent/tools/rag_tool.py` and run the agent with `RETRIEVAL_MODE=rag`.

## 4. Clean up (do this!)

```bash
cd rag
terraform destroy -var="project_id=$GOOGLE_CLOUD_PROJECT"
```
