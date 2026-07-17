#!/usr/bin/env python3
"""Eval runner for the HR Policy Agent — used in Lab 2 (evals & hillclimbing).

Two grading layers:

  1. FLOOR (default, fast, free): deterministic checks. Factual cases must contain
     all `expected_substrings`; refusal cases must contain a refusal phrase. This is
     cheap and ungameable-by-an-LLM, so it's always run as a sanity guard.

  2. JUDGE (--judge on): an LLM grades each answer against the rubric in
     policy_eval.json across several dimensions (0/1/2), producing a score /100 and
     a run-over-run delta so you can watch the score climb. See evals/RUBRICS.md.

Usage:
    # fast floor only (quick inner loop)
    uv run python evals/run_eval.py --mode okf --target agent

    # full rubric scoring with the LLM judge
    uv run python evals/run_eval.py --mode okf --target agent --judge on

    # quick 3-case smoke subset while iterating
    uv run python evals/run_eval.py --mode okf --target agent --judge on --subset smoke

    # score both brains side by side
    uv run python evals/run_eval.py --target agent --judge on --compare-modes

Judge model: set EVAL_JUDGE_MODEL (default gemini-2.5-flash). It should be a
different, ideally stronger model than the agent under test.
"""
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

REFUSAL_HINTS = [
    "don't have", "do not have", "not on file", "no policy", "cannot", "can't",
    "unable", "only assist", "only help", "outside", "decline", "not able to",
    "does not contain", "not contain", "not covered", "not in the handbook",
    "no information", "doesn't cover", "does not cover", "no policy on file",
]

DIM_ORDER = ["correctness", "grounding", "reasoning", "abstention", "citation"]
LAST_RUN = os.path.join(HERE, "last_run.json")
HISTORY = os.path.join(HERE, "history.jsonl")


# --------------------------------------------------------------------------- #
# Agent wiring (same pattern as Lab 1)
# --------------------------------------------------------------------------- #
def load_agent(target: str):
    import agent.agent as runner
    if target == "solution":
        from solution.agent import root_agent
    else:
        root_agent = runner.root_agent
        if root_agent is None:
            sys.exit("agent/agent.py root_agent is None — implement it, or use --target solution.")
    runner.root_agent = root_agent
    return runner


# --------------------------------------------------------------------------- #
# Layer 1 — the floor (deterministic)
# --------------------------------------------------------------------------- #
def floor_check(answer: str, case: dict):
    low = answer.lower()
    if case["expect_refusal"]:
        if any(h in low for h in REFUSAL_HINTS):
            return True, "refused as expected"
        return False, "expected a refusal, got a substantive answer"
    missing = [s for s in case["expected_substrings"] if s.lower() not in low]
    if missing:
        return False, f"missing: {missing}"
    return True, "all expected substrings present"


# --------------------------------------------------------------------------- #
# Layer 2 — the LLM judge (rubric scoring)
# --------------------------------------------------------------------------- #
def evidence_to_str(evidence: list, limit: int = 8000) -> str:
    """Flatten the retrieved-tool payloads into text for the judge."""
    if not evidence:
        return "(the agent retrieved nothing)"
    parts = []
    for e in evidence:
        payload = e.get("payload")
        parts.append(f"[tool: {e.get('tool')}] {json.dumps(payload, default=str)[:limit]}")
    return "\n\n".join(parts)[: limit * 2]


JUDGE_INSTRUCTIONS = """You are a STRICT evaluator of an HR Policy Agent that answers \
questions about the Altostrat Singapore Employee Policy Handbook. The agent must be \
grounded in the RETRIEVED EVIDENCE, cite its source, and REFUSE when the evidence \
does not cover the question. You are a harsh grounding checker, not a helpful assistant.

Score ONLY the dimensions listed. Each score is an integer 0, 1, or 2.

Scoring rules (apply harshly):
- GROUNDING: if the answer states any fact NOT present in RETRIEVED EVIDENCE, score
  grounding 0 even if the fact happens to be true. "Plausible" is not "supported".
- If RETRIEVED EVIDENCE is empty AND the answer makes substantive policy claims,
  grounding = 0.
- REFUSAL cases (the ground-truth notes say to refuse / no policy exists): a clear
  refusal earns abstention = 2; a fabricated answer earns 0 on grounding and abstention.
- REASONING/gotcha: 2 only if the answer catches the trap (a value under a spend
  limit does NOT make a prohibited category — gift cards, adult entertainment —
  allowed) or shows the required calculation; 0 if it falls for the trap.
- Do NOT reward confident tone. Score each dimension independently.

Return STRICT JSON only, no markdown fences, mapping each requested dimension to
{"score": 0|1|2, "why": "one short line"}."""


def build_judge_prompt(case, rubric, answer, evidence_str):
    dims = case["dimensions"]
    dim_lines = "\n".join(
        f"- {d}: {rubric['dimensions'][d]['desc']}" for d in dims
    )
    gt = case.get("ground_truth_notes") or "(none)"
    gotcha = case.get("gotcha")
    gotcha_line = f"\nGOTCHA TO CATCH: {gotcha}" if gotcha else ""
    srcs = case.get("expected_sources") or []
    src_line = (
        f"\n=== ACCEPTABLE SOURCES (for the citation dimension) ===\n"
        f"A correct answer should cite the handbook section it used. Any of these "
        f"handbook sections is an acceptable citation: {srcs}. The handbook repeats "
        f"some topics across sections, so ANY section that genuinely supports the "
        f"answer counts; a missing, wrong, or fabricated citation does not.\n"
        if srcs else ""
    )
    return f"""{JUDGE_INSTRUCTIONS}

=== QUESTION ===
{case['query']}

=== GROUND-TRUTH NOTES (what a correct answer must reflect) ==={gotcha_line}
{gt}
{src_line}
=== RETRIEVED EVIDENCE (what the agent actually retrieved) ===
{evidence_str}

=== AGENT ANSWER (verbatim) ===
{answer}

=== DIMENSIONS TO SCORE ===
{dim_lines}

Return JSON with exactly these keys: {dims}
"""


def _parse_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def judge_case(case, rubric, answer, evidence_str, model, n=1):
    """Call the LLM judge n times; return {dim: median_score} + justifications."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    prompt = build_judge_prompt(case, rubric, answer, evidence_str)
    runs = []
    justifications = {}
    for _ in range(n):
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json"
            ),
        )
        parsed = _parse_json(resp.text)
        scores = {}
        for d in case["dimensions"]:
            entry = parsed.get(d, {})
            scores[d] = int(entry.get("score", 0))
            justifications[d] = entry.get("why", "")
        runs.append(scores)
    median = {d: int(statistics.median([r[d] for r in runs])) for d in case["dimensions"]}
    return median, justifications


def score_case(case, rubric, dim_scores):
    """Weighted per-case percentage over the applicable dimensions, with the
    grounding gate (a fabricated answer can't score 'mostly right')."""
    num = den = 0
    for d in case["dimensions"]:
        w = rubric["dimensions"][d]["weight"]
        num += w * dim_scores[d]
        den += w * 2
    pct = num / den if den else 0.0
    if dim_scores.get("grounding") == 0:
        pct = min(pct, rubric.get("gates", {}).get("grounding_zero_caps_case_at", 0.40))
    return pct


# --------------------------------------------------------------------------- #
# Run one suite
# --------------------------------------------------------------------------- #
def run_suite(cases, rubric, runner, use_judge, judge_model, n):
    results = []
    for c in cases:
        try:
            answer, evidence = runner.run_query_traced(c["query"])
        except Exception as e:  # noqa: BLE001
            results.append({"id": c["id"], "error": str(e)})
            continue
        floor_pass, floor_why = floor_check(answer, c)
        row = {"id": c["id"], "floor_pass": floor_pass, "floor_why": floor_why}
        if use_judge:
            try:
                dim_scores, why = judge_case(c, rubric, answer, evidence_to_str(evidence), judge_model, n)
                row["dims"] = dim_scores
                row["why"] = why
                row["pct"] = score_case(c, rubric, dim_scores)
            except Exception as e:  # noqa: BLE001
                row["error"] = f"Judge error ({e})"
        results.append(row)
    return results


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def print_report(results, use_judge, mode, target, rubric):
    floor_pass = sum(1 for r in results if r.get("floor_pass"))
    n = len(results)

    if not use_judge:
        for r in results:
            if "error" in r:
                print(f"[ERROR] {r['id']}: {r['error']}")
            else:
                print(f"[{'PASS' if r['floor_pass'] else 'FAIL'}] {r['id']} — {r['floor_why']}")
        print(f"\nFLOOR: {floor_pass}/{n} passed  (mode={mode}, target={target})")
        return None

    # columns derived from the rubric (so an added dimension actually shows up)
    dim_order = list(rubric.get("dimensions", {}).keys()) or DIM_ORDER
    hdr = "case".ljust(30) + "".join(d[:4].rjust(6) for d in dim_order) + "   case%"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in results:
        if "error" in r:
            print(f"{r['id'][:29].ljust(30)}  ERROR: {r['error']}")
            continue
        cells = "".join((str(r["dims"][d]) if d in r.get("dims", {}) else "-").rjust(6) for d in dim_order)
        pct_str = f"{r['pct']*100:5.0f}" if "pct" in r else "  N/A"
        print(f"{r['id'][:29].ljust(30)}{cells}   {pct_str}")
    scored = [r for r in results if "pct" in r]
    total = 100 * sum(r["pct"] for r in scored) / len(scored) if scored else 0.0
    print("-" * len(hdr))
    print(f"{'TOTAL'.ljust(30)}{''.join(' ' * 6 for _ in dim_order)}   {total:5.1f} / 100")
    print(f"FLOOR (deterministic): {floor_pass}/{n} passed")

    # anti-gaming alarms
    s1 = [r["id"] for r in scored if not r.get("floor_pass") and r["pct"] > 0.7]
    if s1:
        print(f"⚠  SUSPECT (judge high but floor failed — check phrasing/grader): {s1}")
    s2 = [r["id"] for r in scored if r.get("floor_pass") and r["dims"].get("grounding") == 0]
    if s2:
        print(f"⚠  SUSPECT (floor passed but GROUNDING=0 — likely hardcoded/ungrounded): {s2}")

    # badge (gates)
    gates = rubric.get("gates", {})
    hard = gates.get("hard_cases", [])
    thr = gates.get("badge_min_on_hard_cases", 0.8)
    if hard:
        by_id = {r["id"]: r["pct"] for r in scored}
        got = {h: by_id.get(h) for h in hard if h in by_id}
        ok = got and all(v >= thr for v in got.values())
        fails = [h for h, v in got.items() if v < thr]
        print(f"BADGE (>= {int(thr*100)}% on hard cases {hard}): "
              f"{'✅ PASS' if ok else '❌ not yet'}"
              + (f" — below bar: {fails}" if fails else ""))
    return {"total": total, "per_case": {r["id"]: r["pct"] for r in scored}}


def show_delta_and_save(summary, mode, target):
    key = f"{mode}:{target}"
    prev = {}
    if os.path.exists(LAST_RUN):
        try:
            prev = json.load(open(LAST_RUN)).get(key, {})
        except Exception:  # noqa: BLE001
            prev = {}
    if prev:
        d = summary["total"] - prev.get("total", 0)
        arrow = "↑" if d > 0 else ("↓" if d < 0 else "=")
        print(f"\nDELTA vs last {key} run: {prev.get('total', 0):.1f} -> {summary['total']:.1f}  ({d:+.1f}) {arrow}")
        regressions = [
            cid for cid, p in summary["per_case"].items()
            if cid in prev.get("per_case", {}) and p < prev["per_case"][cid] - 1e-9
        ]
        if regressions:
            print(f"⚠  regressions: {regressions}")
    else:
        print(f"\n(baseline saved for {key} — re-run after a change to see the delta)")

    all_runs = {}
    if os.path.exists(LAST_RUN):
        try:
            all_runs = json.load(open(LAST_RUN))
        except Exception:  # noqa: BLE001
            all_runs = {}
    stamped = {**summary, "timestamp": datetime.now(timezone.utc).isoformat()}
    all_runs[key] = stamped
    json.dump(all_runs, open(LAST_RUN, "w"), indent=2)
    with open(HISTORY, "a") as fh:
        fh.write(json.dumps({"key": key, **stamped}) + "\n")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="HR Policy Agent eval runner")
    ap.add_argument("--mode", choices=["okf", "rag", "hybrid"], help="override RETRIEVAL_MODE")
    ap.add_argument("--target", choices=["solution", "agent"], default="agent")
    ap.add_argument("--eval-file", default=os.path.join(HERE, "policy_eval.json"))
    ap.add_argument("--judge", choices=["on", "off"], default="off")
    ap.add_argument("--subset", choices=["smoke", "full"], default="full")
    ap.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--self-consistency", type=int, default=1, help="judge N times, take median")
    ap.add_argument("--compare-modes", action="store_true", help="run okf and rag side by side")
    args = ap.parse_args()

    data = json.load(open(args.eval_file))
    rubric = data.get("rubric", {})
    cases = data["cases"]
    if args.subset == "smoke":
        cases = [c for c in cases if c.get("smoke")] or cases
    use_judge = args.judge == "on"

    modes = ["okf", "rag"] if args.compare_modes else [args.mode or os.getenv("RETRIEVAL_MODE", "okf")]
    summaries = {}
    for mode in modes:
        os.environ["RETRIEVAL_MODE"] = mode
        # reload config + agent so the mode change takes effect
        for m in ("agent.config", "agent.agent"):
            sys.modules.pop(m, None)
        runner = load_agent(args.target)
        print(f"\n===== mode={mode} | target={args.target} | judge={args.judge} | subset={args.subset} =====")
        results = run_suite(cases, rubric, runner, use_judge, args.judge_model, args.self_consistency)
        summary = print_report(results, use_judge, mode, args.target, rubric)
        if summary:
            summaries[mode] = summary

    if use_judge and not args.compare_modes and summaries:
        show_delta_and_save(summaries[modes[0]], modes[0], args.target)
    if use_judge and args.compare_modes and len(summaries) == 2:
        print("\n===== okf vs rag =====")
        for cid in summaries["okf"]["per_case"]:
            o = summaries["okf"]["per_case"].get(cid, 0) * 100
            r = summaries["rag"]["per_case"].get(cid, 0) * 100
            print(f"{cid[:32].ljust(33)} okf {o:5.0f}   rag {r:5.0f}   Δ {o-r:+.0f}")
        print(f"{'TOTAL'.ljust(33)} okf {summaries['okf']['total']:5.1f}   rag {summaries['rag']['total']:5.1f}")


if __name__ == "__main__":
    main()
