"""HR Policy Agent — entry point.

The runner/session/CLI plumbing below is GIVEN. Your job is the one marked block:
build the `root_agent`. You will also implement the tools it uses
(agent/tools/*.py) and its instructions (agent/prompt.py).

Run it:
    uv run python -m agent.agent "How many days of paid outpatient sick leave do I get?"
    uv run python -m agent.agent --interactive
    uv run adk web .            # then pick "agent" in the web UI
"""
import asyncio
import sys

from google.adk.agents import LlmAgent  # noqa: F401  (used in the TODO block)

from . import config
from .prompt import POLICY_AGENT_PROMPT


# ---------------------------------------------------------------------------
# GIVEN: tool selection. Picks the retrieval "brain" based on RETRIEVAL_MODE.
# ---------------------------------------------------------------------------
def select_tools(mode: str):
    """Return the list of tool callables for the given retrieval mode."""
    tools = []
    if mode in ("okf", "hybrid"):
        from .tools.okf_tool import list_concepts, read_concept
        tools += [list_concepts, read_concept]
    if mode in ("rag", "hybrid"):
        from .tools.rag_tool import search_policy_docs
        tools += [search_policy_docs]
    if not tools:
        raise ValueError(f"Unknown RETRIEVAL_MODE: {mode!r} (use okf | rag | hybrid)")
    return tools


# ===========================================================================
# TODO(you): Build the HR Policy Agent.
#
# Construct an ADK LlmAgent and assign it to `root_agent`. It should use:
#   - model:       config.GEMINI_MODEL
#   - name:        a short identifier, e.g. "hr_policy_agent"
#   - description: one line describing what it does
#   - instruction: POLICY_AGENT_PROMPT  (you write this in agent/prompt.py)
#   - tools:       select_tools(config.RETRIEVAL_MODE)
#
# HINT: from google.adk.agents import LlmAgent  (already imported above)
#       root_agent = LlmAgent(model=..., name=..., description=..., instruction=..., tools=...)
#
# Suggested coding-agent prompt:
#   "In agent/agent.py, build an ADK LlmAgent named hr_policy_agent using
#    config.GEMINI_MODEL, POLICY_AGENT_PROMPT as the instruction, and
#    select_tools(config.RETRIEVAL_MODE) as its tools. Assign it to root_agent."
# ===========================================================================
root_agent = None  # <-- replace this with your LlmAgent(...)


# ---------------------------------------------------------------------------
# GIVEN: a tiny CLI runner so you can talk to the agent from the terminal.
# ---------------------------------------------------------------------------
_session_service = None


def _ensure_runner():
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    global _session_service
    if root_agent is None:
        raise SystemExit(
            "root_agent is None — implement the TODO block in agent/agent.py first."
        )
    if _session_service is None:
        _session_service = InMemorySessionService()
    return Runner(app_name=config.APP_NAME, agent=root_agent, session_service=_session_service)


def _ensure_session(user_id, session_id):
    """Create the session, tolerating both sync and async ADK builds."""
    try:
        _session_service.create_session_sync(
            app_name=config.APP_NAME, user_id=user_id, session_id=session_id
        )
    except AttributeError:
        asyncio.run(
            _session_service.create_session(
                app_name=config.APP_NAME, user_id=user_id, session_id=session_id
            )
        )
    except Exception:
        pass  # already exists


def run_query(query: str, user_id: str = "learner", session_id: str = "session-1") -> str:
    answer, _evidence = run_query_traced(query, user_id=user_id, session_id=session_id)
    return answer


def run_query_traced(query: str, user_id: str = "learner", session_id: str = "session-1"):
    """Like run_query, but also returns the evidence the agent retrieved.

    Returns (answer, evidence) where evidence is a list of
    {"tool": <tool name>, "payload": <the tool's return value>} — i.e. exactly
    what each retrieval tool handed back to the model. The eval harness uses this
    to check *grounding* (did the answer stick to what was retrieved?).
    """
    from google.genai import types

    runner = _ensure_runner()
    _ensure_session(user_id, session_id)
    message = types.Content(role="user", parts=[types.Part(text=query)])
    final = ""
    evidence = []
    for event in runner.run(user_id=user_id, session_id=session_id, new_message=message):
        if not (event.content and event.content.parts):
            continue
        for part in event.content.parts:
            fr = getattr(part, "function_response", None)
            if fr is not None:
                evidence.append({"tool": getattr(fr, "name", "?"), "payload": fr.response})
        if event.is_final_response() and event.content.parts:
            texts = [p.text for p in event.content.parts if getattr(p, "text", None)]
            if texts:
                final = "\n".join(texts)
    return final, evidence


def _interactive():
    print(f"HR Policy Agent [{config.RETRIEVAL_MODE}] — type 'exit' to quit.")
    while True:
        try:
            q = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            print(f"\nagent > {run_query(q)}")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "--interactive":
        _interactive()
    elif argv:
        print(run_query(" ".join(argv)))
    else:
        print('Usage: uv run python -m agent.agent "<question>"  |  --interactive')


if __name__ == "__main__":
    main()
