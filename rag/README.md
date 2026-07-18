# Track A — Vertex AI Search (RAG) setup

This provisions the RAG "brain": a Vertex AI Search data store built from the
handbook PDF. Your agent's `search_policy_docs` tool queries it.

> 💸 **Cost:** Vertex AI Search is a billable, enterprise-tier service. **Clean up when you finish the lab** (Step 4 below).

## Prerequisites

- A GCP project with billing enabled, and the Discovery Engine API enabled:
  ```bash
  gcloud services enable discoveryengine.googleapis.com --project "$GOOGLE_CLOUD_PROJECT"
  gcloud auth application-default login
  ```
- Set `GOOGLE_CLOUD_PROJECT`, `VERTEX_AI_DATA_STORE_ID`, `VERTEX_AI_SEARCH_ENGINE_ID`
  in your `.env` (defaults match the setup defaults).

---

## 1. Provision the bucket + data store + engine

You can provision the infrastructure using **either** the Python script (recommended if Terraform is not installed) **or** Terraform:

### Option 1: Python Provisioning (No Terraform required)

```bash
uv run python rag/provision-rag.py --project "$GOOGLE_CLOUD_PROJECT"
```

### Option 2: Terraform / OpenTofu

If `terraform` is not installed on your machine, install the standalone binary in one command:
```bash
mkdir -p ~/.local/bin
curl -fsSL https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_amd64.zip -o /tmp/terraform.zip
unzip -qo /tmp/terraform.zip -d ~/.local/bin/
export PATH="$HOME/.local/bin:$PATH"
```

Then initialize and apply:
```bash
cd rag
terraform init
terraform apply -var="project_id=$GOOGLE_CLOUD_PROJECT"
cd ..
```

---

## 2. Ingest / index the documents

```bash
uv run python rag/ingest-docs.py --project "$GOOGLE_CLOUD_PROJECT"
```

Indexing can take several minutes. Re-running re-indexes (full reconciliation).

---

## 3. Verify retrieval

```bash
uv run python rag/verify-rag-search.py --query "outpatient sick leave and medical certificate"
# no cloud yet? try the offline mock:
uv run python rag/verify-rag-search.py --mock --query "sick leave"
```

You should see titles + citation links. Once this looks right, implement
`agent/tools/rag_tool.py` and run the agent with `RETRIEVAL_MODE=rag`.

---

## 4. Clean up (do this!)

To delete the Vertex AI Search data store, engine, and GCS bucket:

- **If you used Python:**
  ```bash
  uv run python rag/provision-rag.py --project "$GOOGLE_CLOUD_PROJECT" --destroy
  ```
- **If you used Terraform:**
  ```bash
  cd rag
  terraform destroy -var="project_id=$GOOGLE_CLOUD_PROJECT"
  cd ..
  ```
