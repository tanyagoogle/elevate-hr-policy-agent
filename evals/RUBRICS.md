# The Rubric — how the agent is graded

An **eval** is a test with known-good answers. A **rubric** is the scorecard that
turns each answer into a number. Substring matching ("does the answer contain '14'?")
is a weak rubric — it can't tell whether the agent *made the number up* or *cited the
wrong policy*. This rubric fixes that.

Every answer is scored on up to **5 dimensions**, each **0 / 1 / 2**, then rolled up
to a **score out of 100**. The rubric lives in `evals/policy_eval.json` (the `rubric`
block) so the grader and this document never drift apart.

## The 5 dimensions

| Dimension | Weight | What it asks | 2 (full) | 1 (partial) | 0 (fail) |
|---|---|---|---|---|---|
| **Correctness** | 3 | Are the facts right, all parts answered? | every required fact correct | one part right, one missing/wrong | key fact wrong or absent |
| **Grounding** | 3 | Did it stick to the retrieved policy? | every claim supported by retrieved text | one unsupported embellishment | a fabricated fact / outside knowledge |
| **Reasoning (gotcha)** | 3 | Did it catch the trap / show the math? | names the prohibition or shows the calc | right answer, reasoning implicit | falls for the trap / wrong math |
| **Abstention** | 2 | Answer-vs-refuse decision | answers when covered, refuses when not | right instinct but hedges | answers what it should refuse (or vice-versa) |
| **Citation** | 1 | Did it cite the right source? | correct `Sources:` link | present but wrong/generic | none, or a fabricated source |

Not every dimension applies to every question (a refusal case has no "Correctness";
a simple lookup has no "gotcha"). Inapplicable dimensions are **dropped** and the
weights **renormalized**, so a case is only judged on what's relevant.

## How a case score is computed

```
case %  =  Σ (weight × score)  /  Σ (weight × 2)     over the applicable dimensions
```

Example — the `$45 gift card` gotcha, answered *correctly* ("no, gift cards are
prohibited; the $50 limit doesn't apply"): correctness 2, grounding 2, reasoning 2,
citation 2 → `(3·2 + 3·2 + 3·2 + 1·2) / (3·2 + 3·2 + 3·2 + 1·2)` = **100%**.

Answered *wrong* ("$45 is under $50, so it's fine"): reasoning 0, and likely
correctness 1, grounding 1 → the score collapses to ~**35%**.

**Total = the average of the case percentages × 100.** All cases weigh equally, so no
single question dominates the number you're improving.

## Two "gates" (guardrails against gaming)

- **Grounding gate:** if a case scores **grounding = 0** (it made something up), that
  case is capped at **40%** no matter how good it looks otherwise. A confident,
  fabricated answer is never "mostly right."
- **Badge:** to "pass" the lab, you need **≥ 80%** on the four hard cases (both
  gotchas + both refusals) — the ones that separate real grounding from lucky
  keyword matches.

## Two graders, on purpose

1. **Floor** (`--judge off`, default): the old deterministic substring/refusal check.
   Fast, free, and impossible for an LLM judge to talk its way around. Always runs.
2. **Judge** (`--judge on`): an LLM grades the 5 dimensions using the ground-truth
   notes **and the evidence the agent actually retrieved** (so it can catch "right
   answer, but from thin air").

If the judge gives a high score but the **floor fails**, the runner prints a
`⚠ SUSPECT` line — trust the floor and go look.

## How to *read* a result (this is the skill)

When you run `--judge on`, you get a scoreboard like:

```
case                            corr  grou  reas  abst  cita   case%
room_salon_gotcha                  1     2     0     -     1      45
```

Don't just read the total. Read **which dimension is low**, because that tells you
**what to fix**:

- low **Reasoning** on a gotcha → the agent found the price rule but not the
  prohibition → a **prompt** or **retrieval** problem (make it read all governing
  concepts / check prohibitions first).
- low **Grounding** → it's inventing facts → tighten the **prompt's** "only answer
  from retrieved text" rule.
- low **Citation** → fix the **prompt's** citation instruction or the **tool** so the
  source link is available.
- low **Abstention** → it answered something it shouldn't → strengthen the refusal rule.

That mapping — *symptom → dimension → lever* — is the whole game in `LAB_EVALS.md`.

## Thinking like an eval author

A good rubric is **discriminating** (a better answer scores higher), **grounded**
(rewards using the source, not guessing), and **hard to game** (keyword-stuffing
doesn't win). In Lab 2 you'll not only *use* this rubric — you'll **critique and
extend it** (add a dimension or a case), which is how you learn where any rubric,
including this one, is blind.
