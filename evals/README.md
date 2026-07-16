# Evaluation

`policy_eval.json` holds golden cases (reused from `elevate-hr-agent`'s
`rag_eval_golden` set, plus refusal cases). `run_eval.py` runs them through the
agent and grades expected facts / refusals.

Run the **same** eval against both brains and compare:

```bash
# OKF brain (no cloud) — grades YOUR implementation in agent/
uv run python evals/run_eval.py --mode okf --target agent

# RAG brain (after Track A setup)
uv run python evals/run_eval.py --mode rag --target agent
```

Answer generation needs Gemini credentials (`GEMINI_API_KEY` in `.env`). RAG mode
also needs a provisioned Vertex data store (see `rag/README.md`).

## The interesting cases

- `host_gift_card_gotcha` and `room_salon_gotcha` are **gotchas**: a value under a
  spending limit does not make a *prohibited category* (gift cards, adult
  entertainment) allowed. Note whether each brain gets these right — deliberate OKF
  navigation often beats semantic RAG chunks here.
- `ungrounded_policy` (pet adoption) must be **refused**, not fabricated.
