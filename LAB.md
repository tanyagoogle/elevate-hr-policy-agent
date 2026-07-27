# Lab: Build the HR Policy Agent (RAG vs OKF)

You'll build one grounded HR Policy Agent, give it two interchangeable retrieval
brains, and compare them. **Drive your AI coding agent** (`agy`) to write the code — each
step has a hint and a ready-to-paste prompt.

Time: ~90 minutes. Track B (OKF) needs no cloud; Track A (RAG) needs a GCP project.

---

## The scenario & what you're building

**Context.** Altostrat Singapore's rules live in one 52-page PDF — the *Employee
Policy Handbook & Conduct Guidelines* (`data/handbook.pdf`). Employees flood HR with
the same questions (sick leave, expenses, vacation, gifts), answers are inconsistent,
and some questions are **traps** — e.g. a $45 gift card is *prohibited* even though
it's under the $50 host-gift limit.

**Your mission (Project Elevate).** Build an **HR Policy Assistant**: an ADK
`LlmAgent` (Gemini) that answers an employee's policy question **only** from the
handbook, **cites** the source, and **refuses** when the answer isn't there (no
guessing).

**How it works.** The agent uses **tools** to fetch the right policy, then answers
from what it fetched. You'll give it two interchangeable retrieval "brains":
- **OKF** (Track B): navigate a curated markdown knowledge bundle — no cloud.
- **RAG** (Track A): semantic search over the handbook in **Vertex AI Search**.

Same agent, same prompt, same eval — swap the brain, compare the results. The
handbook is the agent's **single source of truth**; everything it says must trace
back to it. (Full framing in `README.md`.)

---

## 00 — Setup

```bash
uv sync
cp .env.example .env
uvx --python 3.11 google-agents-cli setup   # equips your coding agent with ADK skills
```

Configure your model authentication in `.env` (choose **Path A** or **Path B**):
- **Path A (Gemini API Key):** Set `GEMINI_API_KEY` in `.env` ([get API key](https://aistudio.google.com/apikey)).
- **Path B (Vertex AI):** Authenticate with `gcloud` and enable Vertex AI in `.env`:
  ```bash
  gcloud auth application-default login
  gcloud config set project YOUR_PROJECT_ID
  ```
  In `.env`, comment out `GEMINI_API_KEY` and set `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT=your_gcp_project_id_here`, and `GOOGLE_CLOUD_LOCATION=global`.
  *(Disclaimer: For preview models like `gemini-3.5-flash` on Vertex AI, set `GOOGLE_CLOUD_LOCATION=global` to avoid regional routing 404 errors).*

Sanity checks:

```bash
uv run python knowledge/check_okf.py knowledge     # OKF bundle is well-formed
uv run python -c "import agent.config as c; print('mode:', c.RETRIEVAL_MODE)"
```

---

## 00.5 — Launch Your Coding Agent & Start Coding

Open your terminal in the repository root and start **your coding agent**:

```bash
agy
```

Keep your coding agent open. For each exercise below, copy the **Suggested coding-agent prompt** and paste it directly into your coding agent to have it generate and edit the code for you!

---

## 01 — Meet the agent (and watch it fail)

The scaffold has no retrieval brain and no `root_agent` yet.

```bash
uv run python -m agent.agent "How many days of bereavement leave do I get?"
```

You'll get: `root_agent is None — implement the TODO block in agent/agent.py`.
That's expected. By the end of Track B it will answer, grounded and cited.

---

## 02 — Concept: RAG vs OKF

Read the comparison table in `README.md`. The one-liner:

> **RAG guesses semantically; OKF navigates deliberately.**

- **RAG**: you ingest the handbook PDF into Vertex AI Search; a tool does a semantic
  query and returns chunks.
- **OKF**: the handbook is already curated into `knowledge/` — cross-linked markdown
  concepts with YAML frontmatter. The agent lists concepts and reads the right one.

Browse `knowledge/index.md` (the map) and open one concept, e.g.
`knowledge/01-paid-time-off-leave-operations/1.2-paid-vacation-leave-singapore.md`.
Notice the frontmatter (`type`, `title`, `source`) and that the body is the
handbook's own text — that structure is what the agent will navigate. A concept's
**id** is its path under `knowledge/` minus `.md`.

---

## 03 — Track B: OKF brain (no cloud)

Build the OKF tools and the prompt, then the agent.

**a) Implement `agent/tools/okf_tool.py`** (`list_concepts`, `read_concept`).
> Prompt your coding agent:
> *"Implement list_concepts and read_concept in agent/tools/okf_tool.py. list_concepts
> walks config.KNOWLEDGE_DIR for .md files (skipping index.md/log.md), parses YAML
> frontmatter, and returns {'concepts':[{id,title,description}]}. read_concept maps a
> concept id (its path under knowledge/ minus .md) to the file, splits frontmatter
> from body, returns {'content','title','resource'} (resource from the `source`
> field). Guard against path traversal."*

Verify:
```bash
uv run python -c "from agent.tools.okf_tool import list_concepts, read_concept; \
  cs=list_concepts()['concepts']; print(len(cs),'concepts'); print(cs[0]['id'])"
```

**b) Write `agent/prompt.py`** — start with a basic starter `POLICY_AGENT_PROMPT`.
> Prompt your coding agent:
> *"In agent/prompt.py, write a basic POLICY_AGENT_PROMPT for the Altostrat HR Policy Assistant telling it to answer employee HR policy questions using the available retrieval tools."*

**c) Build the agent** — fill the TODO block in `agent/agent.py`.
> Prompt your coding agent:
> *"In agent/agent.py, build an ADK LlmAgent named hr_policy_agent using config.GEMINI_MODEL, POLICY_AGENT_PROMPT, and select_tools(config.RETRIEVAL_MODE), assigned to root_agent."*

Run it — try a basic lookup, a **gotcha**, and an **out-of-scope** question:
```bash
RETRIEVAL_MODE=okf uv run python -m agent.agent "How many days of bereavement leave do I get?"
RETRIEVAL_MODE=okf uv run python -m agent.agent "Can I expense a \$45 gift card for my host?"
RETRIEVAL_MODE=okf uv run python -m agent.agent "Can you write me a Python function that reverses a string?"

# Or run interactively via ADK / agents-cli:
agents-cli playground                    # launches web UI at http://127.0.0.1:8080/dev-ui/?app=agent
uv run adk run agent "How many days of bereavement leave do I get?"
```

Notice how it performs: the basic question answers well, but with a naive starter prompt, the agent will likely fail or hallucinate on gotchas (gift cards), missing citations, or out-of-domain requests. **That is intentional!** In Lab 2, you will measure its baseline score and use hillclimbing to diagnose and fix these prompt weaknesses.

---

## 04 — Track A: RAG brain (Vertex AI Search)

Follow **`rag/README.md`**: `terraform apply`, ingest the PDF, and verify:

```bash
# needs a provisioned Vertex data store (see rag/README.md):
uv run python rag/verify-rag-search.py --query "outpatient sick leave and medical certificate"
# no GCP yet? the offline mock still exercises the parser:
uv run python rag/verify-rag-search.py --mock --query "sick leave"
```

Then **implement `agent/tools/rag_tool.py`** (`search_policy_docs`).
> *"Implement search_policy_docs(query) in agent/tools/rag_tool.py using
> google-cloud-discoveryengine: query the engine from config, extract segments and
> links, return {'grounded_context','citations'}. Mirror rag/verify-rag-search.py."*

Run the same question against the RAG brain:
```bash
RETRIEVAL_MODE=rag uv run python -m agent.agent "How many days of paid outpatient sick leave do I get?"
```



---

## 05 — Evaluate & compare

Run the **same** eval against both brains:

```bash
uv run python evals/run_eval.py --mode okf --target agent
uv run python evals/run_eval.py --mode rag --target agent
```

Fill in your own comparison:

| Case | OKF result | RAG result | Notes |
|------|-----------|-----------|-------|
| sick_leave_and_mc | | | |
| vacation_accrual_and_shift | | | |
| ramp_back_time | | | |
| host_gift_card_gotcha | | | did each brain catch that gift cards are prohibited? |
| room_salon_gotcha | | | did each catch that adult entertainment is prohibited regardless of price? |
| ungrounded_policy (pet) | | | did each refuse instead of fabricating? |

Watch the two **gotcha** cases especially — they separate deliberate navigation
from semantic recall.

---

## 06 — Stretch

- **Hybrid brain:** set `RETRIEVAL_MODE=hybrid` (OKF + RAG tools both available) and
  update the prompt to prefer OKF, falling back to RAG for long-tail queries.
- **Add a policy:** add one new concept to `knowledge/` (drop in a markdown file
  with frontmatter, run `check_okf.py`) *and* re-ingest it into Vertex. Compare the
  effort — this is OKF's core advantage.
- **Deploy:** ask your coding agent to use `agents-cli` to deploy the agent to
  Google Cloud.

---

## Reference — the ADK pieces you're using

You don't need to master ADK; you assemble five things (the plumbing is given):

| Piece | What it is | Where |
|---|---|---|
| `LlmAgent` | the agent = model + instruction (prompt) + tools | you build in `agent/agent.py` |
| **tool** | a plain Python function the model may call | `agent/tools/*.py` |
| `Runner` | drives the model↔tool loop until a final answer | given (`agent/agent.py`) |
| **session** | per-conversation memory | given (in-memory) |
| `RETRIEVAL_MODE` | picks the retrieval "brain" (`okf`/`rag`/`hybrid`) | `.env` / env var |

The mental model: **the model reads your prompt, decides which tool to call, reads
what the tool returns, then answers.** Grounding lives in two places — the prompt
(tells it to answer only from tool results and to cite) and the tools (return the
right policy text). If an answer is wrong, one of those two is the cause.

How retrieval differs between the brains:
- **OKF** — `list_concepts()` returns the map; the model picks a concept id and calls
  `read_concept(id)` to read that section. Retrieval = *deliberate navigation*.
- **RAG** — `search_policy_docs(query)` returns the top semantically-similar chunks.
  Retrieval = *similarity search*.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `root_agent is None …` | You haven't built the `LlmAgent` yet — finish the TODO block in `agent/agent.py` (Exercise 03c). |
| `NotImplementedError: Implement …` | The tool/prompt stub isn't filled in yet — that's expected until you implement it. |
| 404 / `model … not found` or auth errors | Model access isn't configured. Set `GEMINI_API_KEY` **or** the Vertex vars — see `.env.example`. |
| `Both GOOGLE_API_KEY and GEMINI_API_KEY are set …` | Harmless warning; set only one key in `.env`. |
| `RuntimeWarning: 'agent.agent' found in sys.modules` / `Deprecated…` | Cosmetic ADK/runpy noise — ignore. |
| Agent answers from memory / won't call a tool | Strengthen the prompt's "retrieve before you answer" rule (Exercise 03b). |
| `adk web` shows no agent | Run it from the repo root (`uv run adk web .`) so it finds the `agent` package. |

---

## Done?

You built one agent two ways and formed an evidence-based opinion on **when to reach
for RAG vs OKF**. A reference implementation is available to instructors on the
`instructor` branch if you'd like to compare approaches afterward.

**Next → [Lab 2: Evals & Hillclimbing](LAB_EVALS.md)** — now measure your agent
against a rubric and improve its score the honest way.
