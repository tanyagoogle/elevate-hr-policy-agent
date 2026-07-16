#!/usr/bin/env python3
"""Offline-ish eval runner for the HR Policy Agent.

Runs each case in policy_eval.json through the agent and grades the final answer:
  * expected_substrings : all must appear (case-insensitive) to pass
  * expect_refusal      : answer must decline / say the policy isn't on file

Retrieval happens via the selected RETRIEVAL_MODE. OKF mode needs no cloud; RAG
mode needs a provisioned Vertex data store. Answer generation needs Gemini creds.

Usage:
    uv run python evals/run_eval.py --mode okf --target agent
    RETRIEVAL_MODE=rag uv run python evals/run_eval.py --target agent

(--target solution is available to instructors on the `instructor` branch.)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

REFUSAL_HINTS = [
    "don't have", "do not have", "not on file", "cannot", "can't", "unable",
    "only assist", "only help", "outside", "decline", "not able to",
]


def load_agent(target: str):
    """Wire the chosen root_agent into the given runner (agent.agent)."""
    import agent.agent as runner
    if target == "solution":
        from solution.agent import root_agent
    else:
        root_agent = runner.root_agent
        if root_agent is None:
            sys.exit("agent/agent.py root_agent is None — implement the TODO block in agent/agent.py first.")
    runner.root_agent = root_agent
    return runner


def grade(answer: str, case: dict) -> tuple[bool, str]:
    low = answer.lower()
    if case["expect_refusal"]:
        if any(h in low for h in REFUSAL_HINTS):
            return True, "refused as expected"
        return False, "expected a refusal, got a substantive answer"
    missing = [s for s in case["expected_substrings"] if s.lower() not in low]
    if missing:
        return False, f"missing: {missing}"
    return True, "all expected substrings present"


def main():
    ap = argparse.ArgumentParser(description="HR Policy Agent eval runner")
    ap.add_argument("--mode", choices=["okf", "rag", "hybrid"], help="override RETRIEVAL_MODE")
    ap.add_argument("--target", choices=["solution", "agent"], default="agent")
    ap.add_argument("--eval-file", default=os.path.join(HERE, "policy_eval.json"))
    args = ap.parse_args()

    if args.mode:
        os.environ["RETRIEVAL_MODE"] = args.mode

    cases = json.load(open(args.eval_file))["cases"]
    runner = load_agent(args.target)

    passed = 0
    print(f"\nRunning {len(cases)} cases | mode={os.getenv('RETRIEVAL_MODE', 'okf')} | target={args.target}\n")
    for c in cases:
        try:
            answer = runner.run_query(c["query"])
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {c['id']}: {e}")
            continue
        ok, why = grade(answer, c)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {c['id']} — {why}")
    print(f"\n{passed}/{len(cases)} passed")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
