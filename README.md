# HR Policy Agent Lab — RAG vs OKF

Build **one agent** — an HR Policy Assistant that answers employee questions
grounded in the *Altostrat Singapore Employee Policy Handbook* — and build its
"retrieval brain" **two ways** so you feel the trade-off:

- **Track A — RAG:** Google **Vertex AI Search** over the handbook (semantic search).
- **Track B — OKF:** Google's **Open Knowledge Format** — a cross-linked markdown
  bundle the agent *navigates deliberately* (no vector database).

You write the code by instructing **your AI coding agent** (`agy`).
Every exercise ships a hint and a suggested prompt to paste directly into your coding agent.

---

## The scenario (read this first)

**The company.** Altostrat Singapore employs full-time staff, interns, and an
extended workforce. All their rules live in one place: the **Altostrat Singapore
Employee Policy Handbook & Conduct Guidelines** — a **52-page PDF** (`data/handbook.pdf`)
covering leave, expenses, business courtesies, conduct, privacy, and more.

**The problem.** Employees keep asking HR the same questions — *"How much sick leave
do I get?"*, *"Can I expense this?"*, *"How many vacation days for a 12-hour shift?"*
HR is a bottleneck, answers come out inconsistent, and nobody reads a 52-page PDF.
Some questions are even **traps**: a purchase *under* a dollar limit can still be
**prohibited** (e.g. gift cards, adult entertainment). A confident-but-wrong answer
is a compliance risk.

**The ask (Project Elevate).** Ship a conversational **HR Policy Assistant** that
answers employee policy questions **accurately, grounded strictly in the handbook,
with citations** — and that **refuses** when the answer isn't in the handbook instead
of guessing.

### What the agent *is*
A single, focused **ADK `LlmAgent`** (Gemini) for policy Q&A. Not a freeform chatbot:
it uses **tools** to fetch the relevant policy, then answers from what it fetched.

### What the agent *does*
1. Takes an employee's natural-language question.
2. **Retrieves** the relevant policy — via **RAG** or **OKF** (the two "brains" you build).
3. Answers **only** from that policy, **cites** the source, and **declines**
   out-of-domain or unanswerable questions.

### What the policy handbook *does*
It is the agent's **single source of truth** (its "grounding corpus"). The agent may
answer *only* from it. In this lab the same handbook is given to the agent **two ways**:
a **Vertex AI Search** index (Track A / RAG) and an **OKF markdown bundle** in
`knowledge/` (Track B).

### Why this is the RAG-vs-OKF lesson
Accurate, auditable Q&A over a big document is *exactly* the "how does an agent know
the docs?" problem. RAG and OKF are two answers — and this handbook, with its gotcha
rules, is the perfect place to feel the difference.

---

## What you'll build

The agent is an ADK `LlmAgent` (Gemini). You implement the parts that make it an
agent; the plumbing is given.

| You write | What it does |
|---|---|
| `agent/tools/okf_tool.py` | `list_concepts` / `read_concept` — traverse the OKF bundle |
| `agent/tools/rag_tool.py` | `search_policy_docs` — query Vertex AI Search |
| `agent/prompt.py` | grounding + citation instructions |
| `agent/agent.py` (one block) | construct the `LlmAgent` |

Given for you: the OKF `knowledge/` bundle, the handbook, the Vertex RAG scripts
(`rag/`), the eval set (`evals/`), config, and the runner/CLI.

---

## The three layers (mental model)

```
  YOU  ──talk──▶  CODING AGENT  ──commands+skills──▶  agents-cli  ──▶  THE HR POLICY AGENT
  (a human)       (AI pair programmer,                (a toolkit)       (ADK LlmAgent + Gemini,
                   launched with `agy`)                                 the thing you build)
```

`agents-cli` is a toolkit that teaches your coding agent how to scaffold, run, evaluate, and deploy ADK agents on Google Cloud. Installing it is **encouraged, not required**:

```bash
uvx --python 3.11 google-agents-cli setup      # equips your coding agent with ADK skills
# or install globally: uv tool install --python 3.11 google-agents-cli && agents-cli setup
```

---

## Prerequisites & Setup

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- For **Track A (RAG)** only: a Google Cloud project with billing, Terraform ≥ 1.5, and `gcloud` (see `rag/README.md`).
- Model access — choose **either** Google AI Studio (Gemini API key) **or** Vertex AI via Google Cloud. The Lab 2 judge uses the same auth.

```bash
# 1. Install dependencies
uv sync

# 2. Copy the environment configuration
cp .env.example .env
```

### Choose your Model Authentication Path

#### Path A: Gemini API Key (Google AI Studio)
Simplest for local testing. Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

In `.env`, set:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

#### Path B: Vertex AI (Google Cloud)
Use Vertex AI with your Google Cloud project credentials.

1. Log in with Google Cloud Application Default Credentials (ADC) and set your project:
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

2. In `.env`, comment out `GEMINI_API_KEY` and configure the Vertex AI variables:
```bash
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your_gcp_project_id_here
GOOGLE_CLOUD_LOCATION=global
```

> ⚠️ **Region & Model Disclaimer:** Depending on your Google Cloud project quota and the model tier you are using (e.g. preview models like `gemini-3.5-flash`), you should set `GOOGLE_CLOUD_LOCATION=global` (or your assigned regional location) to avoid `404 / Model Not Found` routing errors.

---

## Quickstart & Coding with Your AI Agent

```bash
# 1. Confirm the OKF knowledge bundle is well-formed
uv run python knowledge/check_okf.py knowledge

# 2. Confirm the scaffold imports and the retrieval mode
uv run python -c "import agent.config as c; print('mode:', c.RETRIEVAL_MODE)"

# 3. Launch your coding agent to start coding!
agy
```

Now open **`LAB.md`**, copy the suggested prompts for each exercise, and paste them into **your coding agent** to implement your agent.

When you've implemented the OKF tools + prompt + agent, test it three ways:

- **A) Local Web UI Playground (Recommended):**
  ```bash
  agents-cli playground      # or: uv run adk web .
  ```
- **B) Interactive Terminal CLI:**
  ```bash
  uv run adk run agent "How many days of bereavement leave do I get?"
  ```
- **C) Standalone Python script:**
  ```bash
  RETRIEVAL_MODE=okf uv run python -m agent.agent "How many days of bereavement leave do I get?"
  ```

---

## RAG vs OKF — the point of the lab

| | RAG (Vertex AI Search) | OKF (Open Knowledge Format) |
|---|---|---|
| Retrieval | Semantic search returns top-k chunks | Agent reads `index.md`, navigates to the right concept, reads it |
| Infra | GCP project, data store, ingest pipeline | None — plain `.md` files ("if you can `cat` a file, you can read it") |
| Best for | Large, messy, unstructured corpora | Curated, structured, stable knowledge |
| Updates | Re-ingest + re-index | Edit a markdown file, commit |
| Auditability | Chunk provenance | Exact file + frontmatter `resource` + git history |
| Gotcha handling | May retrieve a *related* chunk and miss the governing rule | Reads the whole governing concept, cross-links to prohibitions |

> Observed in this lab's own RAG data store: asking *"room salon under $100 — need
> approval?"* returned the **approval-thresholds** chunk but **missed** the
> "adult entertainment is prohibited" chunk — exactly the kind of gap OKF's
> deliberate navigation avoids. You'll see this yourself in Exercise 05.

## Repo map

```
agent/         # the agent you build (scaffold with TODOs)
knowledge/     # the OKF bundle (given, complete) + check_okf.py
rag/           # Track A: terraform + ingest + verify (given)
data/          # handbook.pdf (source corpus)
evals/         # policy_eval.json + run_eval.py + RUBRICS.md
LAB.md         # Lab 1 — build the agent (exercises 00 -> 06)
LAB_EVALS.md   # Lab 2 — evals & hillclimbing (measure & improve the agent)
```

## Two labs

1. **`LAB.md` — Build the agent.** Implement the retrieval tools, prompt, and agent
   (RAG and OKF).
2. **`LAB_EVALS.md` — Evals & hillclimbing.** Measure the agent against a rubric,
   read the scoreboard, and improve the score the honest way (see `evals/RUBRICS.md`).

Start with **`LAB.md`**.
