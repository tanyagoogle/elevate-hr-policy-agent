# Lab 2 — Evals & Hillclimbing

In Lab 1 you built an HR Policy Agent. But **how good is it?** In this lab you'll
learn to *measure* it, *read a rubric*, and *improve the score the honest way* —
by fixing the real weakness, not by memorizing the test.

**Prerequisites**
- Lab 1 finished (a working `agent/` you can run), **or** use `--target solution`
  to work against the reference agent.
- `uv sync` done; model access configured in `.env` (`GEMINI_API_KEY` or Vertex AI).
- The LLM judge (Exercise 1+) makes model calls — uses the same model credentials as the agent.

**The mental model.** An *eval* is a test with known-good answers
(`evals/policy_eval.json`). A *rubric* is the scorecard that turns an answer into a
number (`evals/RUBRICS.md`). *Hillclimbing* is the loop: measure → find the weakest
spot → change one thing → measure again → keep it if the number went up.

> ⚠️ The whole point is to build a genuinely better agent — **not** to hardcode the 7
> answers. At the end, the trainer reveals a *hidden* test to check you didn't cheat.
>
> 💡 **Note on Evaluation Tooling:** In this lab, we use `evals/run_eval.py` because it includes deterministic floor checks tailored specifically to the handbook gotchas (e.g. spend limits and citation rules) without requiring GCP project setup. In production ADK projects on Google Cloud, you can run standardized evaluations across multiple models using `agents-cli eval run`.

---

## Exercise 0 — Measure a baseline

First the fast, free grader (the "floor" — deterministic substring/refusal checks):

```bash
uv run python evals/run_eval.py --mode okf --target agent
```

You get `[PASS]/[FAIL]` per case and `FLOOR: N/7`. That's a coarse signal. Now the
real scorecard — the **LLM judge** grading 5 dimensions (see `evals/RUBRICS.md`):

```bash
uv run python evals/run_eval.py --mode okf --target agent --judge on
```

You'll see a scoreboard and a **TOTAL / 100**. Write it down — this is your baseline.
(The runner also saves it, so the next run prints the change.)

> Iterating fast? Use `--subset smoke` (3 representative cases) for the inner loop,
> and do a full `--judge on` run before you trust a number.

---

## Exercise 1 — Read the scoreboard (eval literacy)

Open `evals/RUBRICS.md` and keep it beside you. Look at your scoreboard:

```
case                            corr  grou  reas  abst  cita   case%
room_salon_gotcha                  1     2     0     -     1      45
```

Answer these for your own run (this is the skill, not busywork):
1. Which **case** is lowest? Which **dimension** is dragging it down?
2. Is it a *wrong answer* (Correctness/Reasoning low) or a *right answer graded low*
   (Grounding/Citation low, or a phrasing miss the floor flagged)?
3. Does a low score mean the agent **retrieved the wrong thing**, or **retrieved the
   right thing and reasoned badly**? (Open the trajectory to check —
   `uv run adk web .` — and see which concept/chunk it actually read.)

The dimension that's low tells you **what kind of fix you need**. That symptom →
dimension → lever mapping is the engine of the next exercise.

---

## Exercise 2 — Diagnose one failure

Pick your lowest case. Write a one-sentence **diagnosis** with a predicted cause, e.g.:

> *"`room_salon_gotcha` scores Reasoning 0 because the agent read the pricing/approval
> concept but not the prohibitions concept, so it concluded 'under $100 → fine'.
> If I make it check prohibitions before applying any dollar limit, Reasoning should
> go to 2 without breaking the passing cases."*

A diagnosis names: the case, the low dimension, the likely root cause, and the fix
you'll try — with a **prediction**. No prediction, no learning.

---

## Exercise 3 — The hillclimb loop

Repeat this loop. **Change exactly one thing per pass** — if two things change and
the score moves, you won't know why.

1. **Measure** (you did — that's your current number).
2. **Read** the weakest case/dimension (Ex 1).
3. **Hypothesize** one cause + fix (Ex 2).
4. **Change ONE lever** (table below).
5. **Re-measure** the same command. Note the delta and *which cases flipped*.
6. **Keep or revert.** Net up with no regressions → keep. Fixed one, broke another →
   **revert** and find the real root cause. Log every run (even reverts).

### Which lever fixes which failure

| Symptom (low dimension) | Lever | File |
|---|---|---|
| Reasoning on a gotcha | tell the agent to check **prohibitions before limits**; read *all* governing concepts | `agent/prompt.py` |
| Grounding (invents facts) | strengthen "answer **only** from retrieved text; else say you don't know" | `agent/prompt.py` |
| Correctness on multi-part Qs | require it to answer **every** sub-question and show the calc | `agent/prompt.py` |
| Right topic, wrong concept read | sharpen concept `description`s / `index.md`; read more than one concept | `agent/tools/okf_tool.py`, `knowledge/index.md` |
| Governing text never retrieved (RAG) | broaden the query; return more segments | `agent/tools/rag_tool.py` |
| Citation missing/wrong | fix citation instruction / ensure the source link is in tool output | `agent/prompt.py`, tools |
| The fact truly isn't there | add a real, spec-conformant concept (run `check_okf.py`) | `knowledge/**.md` |

**Rule of thumb:** behavior/consistency bug → *prompt*; find-the-right-source bug →
*tool logic / index*; fact-missing bug → *knowledge*; fact-there-but-not-retrieved →
*retrieval params*.

### RAG vs OKF tell
If a case **passes under one brain and fails under the other**, the bug is almost
always in **retrieval** (tool/index/params), not the prompt — the prompt is shared.
Compare them directly:

```bash
uv run python evals/run_eval.py --target agent --judge on --compare-modes
```

---

## Exercise 4 — Extend the rubric (think like an eval author)

Using a rubric is half the skill; **designing** one is the other half. The rubric in
`evals/policy_eval.json` is good, not perfect. Do one of these:

- **Add a dimension.** e.g. *Conciseness* (0/1/2) or *Tone/empathy*. Add it to the
  `rubric.dimensions` block (with a weight and description) and to the `dimensions`
  list of the cases it applies to. Re-run `--judge on` and see how scores shift.
- **Add a case.** Write a new question grounded in the handbook (a new gotcha, or a
  multi-part factual). Give it `expected_substrings`, `ground_truth_notes`,
  `expected_sources`, and the `dimensions` it exercises.

Then answer: did your change make the rubric **more discriminating** (better answers
score higher) or just noisier? Where is this rubric still **blind**? (Hint: could a
verbose, hedgy answer still score well? Could a correct answer with an ugly citation
be over-penalized?) Writing evals *is* iterating on your definition of "good."

---

## Exercise 5 — The reveal (don't overfit)

Tell your trainer when your agent is locked. The held-out set
(`evals/policy_eval_heldout.json`) is **provided by your trainer at this point** — it
is intentionally *not* in the learner repo, so you can't tune against it. Once you
have it, run it **once**:

```bash
# your trainer will provide evals/policy_eval_heldout.json first
uv run python evals/run_eval.py --mode okf --target agent --judge on \
  --eval-file evals/policy_eval_heldout.json
```

Record three numbers: **public score**, **held-out score**, and the **gap**.

- Small gap → you built a genuinely better agent. 🎉
- Big gap (high public, low held-out) → you taught to the test (hardcoded facts,
  stuffed the 7 answers into the prompt). The fix is always a **general rule**
  ("a spend limit never overrides a prohibited category"), never a special-case.

**What "good" looks like:** high *and* close public/held-out scores; both gotchas and
both refusals hold on *both* sets; and a run log showing clean one-lever changes with
named root causes.

---

## Reference — the score in one place

Two graders run; understand both:

- **Floor** (always): deterministic. Factual cases need all `expected_substrings`;
  refusal cases need a refusal phrase. Cheap and ungameable-by-an-LLM, so it's a
  guard, not the grade.
- **Judge** (`--judge on`): an LLM scores each answer on the rubric dimensions
  (0/1/2), weighted into a per-case % and a **TOTAL /100**. See `evals/RUBRICS.md`.

Reading a scoreboard row — the low **dimension** tells you the **lever**:

| Low dimension | Likely cause | Where you fix it |
|---|---|---|
| `reason` (on a gotcha) | found the limit, missed the prohibition | prompt / retrieval |
| `grou` (grounding) | inventing facts not in the evidence | prompt |
| `corr` | missed a sub-question or a number | prompt |
| `cita` | wrong/missing source | prompt / tool |
| `abst` | answered something it should refuse | prompt |

Signals the runner prints:
- **`BADGE`** — pass = ≥80% on the four hard cases (both gotchas + both refusals).
- **`DELTA`** — change vs your last run for this mode/target, plus any regressions.
- **`⚠ SUSPECT: floor passed but GROUNDING=0`** — the answer hit the keywords but
  isn't supported by what was retrieved. This is the tell-tale of **hardcoding /
  teaching to the test** — fix it, don't celebrate it.
- **`⚠ SUSPECT: judge high but floor failed`** — usually a phrasing mismatch; inspect.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `root_agent is None` | Finish Lab 1, or use `--target solution` (instructor branch). |
| 404 / auth error from the judge | The judge makes its own model calls — same auth as the agent; set `--judge-model` and creds (see `.env.example`). |
| Score won't move as you iterate | You're changing more than one thing, or fixing the *instance* not the *class*. Change one lever; write a general rule. |
| Added a rubric dimension but total barely changes | Your answers already max it — try a case that stresses it; the new column now shows on the scoreboard. |
| `policy_eval_heldout.json` not found | It's trainer-provided (Exercise 5) — not in the learner repo by design. |
| Judge is slow/expensive | Use `--subset smoke` while iterating; do a full `--judge on` run only to lock a number. |

---

## Wrap-up

> 💸 Run `terraform destroy` (see `rag/README.md`) when you're done — Vertex AI
> Search is billable.

You learned to measure an agent with a rubric, read a scoreboard to find the real
weakness, hillclimb with disciplined one-variable changes, extend a rubric, and prove
generalization on a held-out set. That measure-diagnose-improve loop — not any single
prompt tweak — is the durable skill for shipping agents you can trust.
