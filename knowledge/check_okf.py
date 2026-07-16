#!/usr/bin/env python3
"""OKF v0.1 conformance checker for the HR policy knowledge bundle.

Usage:
    uv run python knowledge/check_okf.py knowledge

Checks (hard failures -> exit 1):
  * every non-reserved .md file has a parseable YAML frontmatter block
  * every frontmatter block has a non-empty `type`
  * the bundle-root index.md declares `okf_version`

Warnings (do not fail the build; per spec, links may point at not-yet-written
knowledge and consumers MUST tolerate broken links):
  * bundle-relative links whose target file does not exist

Depends only on the standard library + PyYAML.
"""
import os
import re
import sys

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML is required: uv sync (installs pyyaml)")
    sys.exit(2)

RESERVED = {"index.md", "log.md"}
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# markdown links whose target ends in .md (absolute /... or relative ./... or bare)
LINK_RE = re.compile(r"\[[^\]]+\]\((?!https?://)([^)]+?\.md)[^)]*\)")


def parse_frontmatter(text):
    """Return (dict_or_None, ok). ok is False when a frontmatter block is
    present but unparseable, or absent entirely."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, False
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None, False
    return data, True


def main(bundle):
    if not os.path.isdir(bundle):
        print(f"[ERROR] not a directory: {bundle}")
        return 1

    errors, warnings, concepts = [], [], 0

    # root index.md must declare okf_version
    root_index = os.path.join(bundle, "index.md")
    if not os.path.isfile(root_index):
        errors.append("missing bundle-root index.md")
    else:
        with open(root_index, encoding="utf-8") as fh:
            data, _ = parse_frontmatter(fh.read())
        if not data or "okf_version" not in data:
            errors.append("root index.md must declare `okf_version` in frontmatter")

    for dirpath, _dirs, files in os.walk(bundle):
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, bundle)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()

            # broken-link check (warn only) for every markdown file
            for target in LINK_RE.findall(text):
                if target.startswith("/"):
                    resolved = os.path.join(bundle, target.lstrip("/"))
                else:
                    resolved = os.path.normpath(os.path.join(dirpath, target))
                if not os.path.isfile(resolved):
                    warnings.append(f"{rel}: broken link -> {target}")

            if name in RESERVED:
                continue

            concepts += 1
            data, ok = parse_frontmatter(text)
            if not ok:
                errors.append(f"{rel}: missing or unparseable YAML frontmatter")
                continue
            if not data.get("type"):
                errors.append(f"{rel}: frontmatter missing non-empty `type`")

    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")

    if errors:
        print(f"\nFAIL: {len(concepts) if isinstance(concepts, list) else concepts} concepts, "
              f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1

    print(f"\nPASS: {concepts} concepts, 0 frontmatter errors, {len(warnings)} broken-link warning(s)")
    return 0


if __name__ == "__main__":
    bundle = sys.argv[1] if len(sys.argv) > 1 else "knowledge"
    sys.exit(main(bundle))
