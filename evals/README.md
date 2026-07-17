# Evaluation

`policy_eval.json` holds golden cases (reused from `elevate-hr-agent`'s
`rag_eval_golden` set, plus gotchas and refusals) **and** the grading rubric.
`run_eval.py` runs them through the agent and grades two ways:

- **Floor** (default): fast, free, deterministic — factual cases must contain the
  `expected_substrings`; refusal cases must contain a refusal phrase.
- **Judge** (`--judge on`): an LLM grades each answer against the rubric across 5
  dimensions → a score **/100**, a scoreboard, and a run-over-run delta.

See **`RUBRICS.md`** for the scorecard, and **`../LAB_EVALS.md`** (Lab 2) for the
full measure → diagnose → improve workflow.

## Quick start

```bash
# fast floor only (quick inner loop) — grades YOUR implementation in agent/
uv run python evals/run_eval.py --mode okf --target agent

# full rubric scoring with the LLM judge
uv run python evals/run_eval.py --mode okf --target agent --judge on

# fast 3-case smoke subset while iterating
uv run python evals/run_eval.py --mode okf --target agent --judge on --subset smoke

# both brains side by side
uv run python evals/run_eval.py --target agent --judge on --compare-modes
```

Answer generation needs model credentials (`GEMINI_API_KEY` or Vertex AI configured in `.env`). The judge
also makes model calls; set `EVAL_JUDGE_MODEL` to override the default
(`gemini-2.5-flash`). RAG mode additionally needs a provisioned Vertex data store
(see `rag/README.md`).

`--target solution` grades the reference agent (available to instructors on the
`instructor` branch). Per-run state (`last_run.json`, `history.jsonl`) is git-ignored.

## The interesting cases

- `host_gift_card_gotcha` and `room_salon_gotcha` are **gotchas**: a value under a
  spending limit does not make a *prohibited category* (gift cards, adult
  entertainment) allowed. Note whether each brain gets these right — deliberate OKF
  navigation often beats semantic RAG chunks here.
- `out_of_domain` (write code) and `ungrounded_policy` (pet adoption) must be
  **refused**, not fabricated.
