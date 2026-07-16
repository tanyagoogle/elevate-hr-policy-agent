"""Track B — OKF retrieval tools.

The agent uses these to *navigate* the Open Knowledge Format bundle in knowledge/:
first list what concepts exist, then read the most relevant one. No vector DB.

You implement two functions. Keep the return shapes exactly as documented — the
prompt and the agent rely on them.
"""
from .. import config  # config.KNOWLEDGE_DIR points at the knowledge/ bundle


def list_concepts() -> dict:
    """List the policy concepts available in the OKF bundle.

    Returns:
        {"concepts": [{"id": str, "title": str, "description": str}, ...]}
        where `id` is the concept path without the .md suffix,
        e.g. "leave/bereavement-leave".
    """
    # TODO(you): walk config.KNOWLEDGE_DIR for *.md files, SKIP the reserved
    #   files index.md and log.md, parse each file's YAML frontmatter, and return
    #   its id/title/description.
    #
    # HINT: a concept id is the path relative to KNOWLEDGE_DIR minus ".md".
    #       Use os.walk + PyYAML (yaml.safe_load) on the block between the first
    #       two "---" lines. See knowledge/check_okf.py for a frontmatter parser.
    #
    # Suggested coding-agent prompt:
    #   "Implement list_concepts(): os.walk config.KNOWLEDGE_DIR, skip index.md and
    #    log.md, parse YAML frontmatter, return {'concepts': [{id,title,description}]}."
    raise NotImplementedError("Implement list_concepts()")


def read_concept(concept_id: str) -> dict:
    """Read one OKF concept's content and citation.

    Args:
        concept_id: e.g. "03-other-compassionate-unpaid-leaves/3.1-bereavement-leave-global" (no .md).

    Returns:
        {"content": str, "title": str, "resource": str | None}
        where `content` is the markdown body (after the frontmatter) and
        `resource` is the frontmatter `source` (or `resource`) reference if present.
    """
    # TODO(you): map concept_id -> config.KNOWLEDGE_DIR/<concept_id>.md, read it,
    #   split frontmatter from body, and return the body + title + source.
    #
    # HINT: a concept_id is the path under knowledge/ minus ".md", e.g.
    #       "03-other-compassionate-unpaid-leaves/3.1-bereavement-leave-global" ->
    #       os.path.join(KNOWLEDGE_DIR, "03-...", "3.1-...global.md"). Guard against
    #       paths that escape the bundle. Return a helpful message if it doesn't exist.
    #       Concept frontmatter uses a `source:` field (the handbook section) for citations.
    #
    # Suggested coding-agent prompt:
    #   "Implement read_concept(concept_id): resolve to KNOWLEDGE_DIR/<id>.md,
    #    parse YAML frontmatter, return {'content','title','resource'} (resource from
    #    the frontmatter `source` field)."
    raise NotImplementedError("Implement read_concept()")
