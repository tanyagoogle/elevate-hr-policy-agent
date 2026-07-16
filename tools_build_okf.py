#!/usr/bin/env python3
"""Build the OKF knowledge bundle VERBATIM from the handbook PDF.

OKF is only a markdown organization of the PDF's own text. This script extracts
the PDF, splits it on SECTION / N.M headings, and writes one concept file per
subsection whose BODY is the handbook's own words (whitespace normalized from the
PDF extraction; bullets preserved). Frontmatter is minimal and source-referenced:
type, verbatim title, and the handbook section reference. No paraphrase, no
invented examples, no fabricated URLs.

Usage:
    python tools_build_okf.py --dry     # manifest + spot-checks, writes nothing
    python tools_build_okf.py --write    # (re)generate knowledge/ concept files
"""
import argparse
import os
import re
import sys

from pypdf import PdfReader

REPO = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(REPO, "data", "handbook.pdf")
KN = os.path.join(REPO, "knowledge")

SEC_RE = re.compile(r"SECTION\s+(\d+)\s*:\s*([A-Z][A-Z].*?)\s*$")
SUB_RE = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+([A-Z].*?)\s*$")


def slug(s):
    s = re.sub(r"[’'&(),/]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)


def normalize_body(lines):
    """Join PDF-fragmented lines into faithful text; keep bullets as markdown."""
    text = "\n".join(lines)
    # bullets: ● -> top-level, ○ -> nested
    text = text.replace("●", "\n●").replace("○", "\n○")
    out_lines = []
    for chunk in text.split("\n"):
        c = re.sub(r"\s+", " ", chunk).strip()
        if not c:
            continue
        if c.startswith("●"):
            out_lines.append("- " + c.lstrip("● ").strip())
        elif c.startswith("○"):
            out_lines.append("  - " + c.lstrip("○ ").strip())
        else:
            # continuation of previous paragraph/bullet
            if out_lines and not out_lines[-1].startswith("#"):
                out_lines[-1] = (out_lines[-1] + " " + c).strip()
            else:
                out_lines.append(c)
    return "\n".join(out_lines).strip()


def parse():
    reader = PdfReader(PDF)
    raw = "\n".join((p.extract_text() or "") for p in reader.pages)
    lines = raw.split("\n")

    sections = {}          # num -> title
    concepts = []          # (sec_num, sub_num, title, [body lines])
    def norm(t):
        return re.sub(r"\s+", " ", t).strip()

    FUNC = {"and", "of", "the", "in", "to", "for", "on", "or", "a", "an", "with", "at", "by", "&"}

    def title_of(remainder):
        """Heuristic frontmatter title = leading Title-case run, stopping where a
        normal sentence begins. Cosmetic only — the full remainder stays in the body,
        so this never drops handbook words."""
        toks = norm(remainder).split()
        n = len(toks)

        def low(t):
            return t[:1].islower()

        cut = min(n, 12)
        for i in range(1, n):
            tk, nxt, aft = toks[i], toks[i + 1] if i + 1 < n else "", toks[i + 2] if i + 2 < n else ""
            # (a) a Title-word beginning a sentence: next & the one after are lowercase
            if re.match(r"^[A-Z][a-z]+$", tk) and low(nxt) and (aft == "" or low(aft)):
                cut = i
                break
            # (b) an "A"/"I" sentence start
            if tk in ("A", "I") and low(nxt):
                cut = i
                break
            # (c) a "<Word> <Month/Word> <digit>" sentence start (e.g. "Effective April 1, 2026")
            if re.match(r"^[A-Z][a-z]+$", tk) and re.match(r"^[A-Z][a-z]+$", nxt) and aft[:1].isdigit():
                cut = i
                break
        return " ".join(toks[:cut]).strip(" :")

    def start_sub(sec_n, sub_n, remainder, clean):
        title = norm(remainder) if clean else title_of(remainder)
        c = {"sec": sec_n, "sub": sub_n, "title": norm(f"{sec_n}.{sub_n} {title}"),
             "body": [] if clean else [remainder]}
        concepts.append(c)
        return c

    cur = None
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m_sec = SEC_RE.search(s)
        if m_sec:
            sec_n = int(m_sec.group(1))
            rest = m_sec.group(2)
            sections.setdefault(sec_n, norm(rest))
            m_embed = re.search(r"(\d{1,2})\.(\d{1,2})\s+([A-Z].*)$", rest)
            if m_embed and int(m_embed.group(1)) == sec_n:
                sections[sec_n] = norm(rest[: m_embed.start()])
                cur = start_sub(sec_n, int(m_embed.group(2)), m_embed.group(3), clean=False)
            else:
                cur = None
            continue
        m_sub = SUB_RE.match(s)
        if m_sub and int(m_sub.group(1)) in sections and int(m_sub.group(2)) <= 20 \
           and " Section " not in s:
            clean = len(s) <= 80 and not s.endswith(".")
            cur = start_sub(int(m_sub.group(1)), int(m_sub.group(2)), m_sub.group(3), clean=clean)
            continue
        if cur is not None:
            cur["body"].append(s)
    return sections, concepts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    sections, concepts = parse()
    print(f"SECTIONS: {len(sections)} | CONCEPTS: {len(concepts)}")

    # spot-check verbatim facts survive
    allbody = "\n".join(normalize_body(c["body"]) for c in concepts)
    checks = ["14 days", "46 work days", "48 hours", "1.5 vacation days",
              "$50 per day", "gift cards", "room salons", "20 work days"]
    print("\nVERBATIM SPOT-CHECKS:")
    for ch in checks:
        print(f"  {'OK ' if ch in allbody else 'MISS'} {ch!r}")

    if args.dry:
        print("\nMANIFEST (first 8 + last 4):")
        for c in concepts[:8] + concepts[-4:]:
            b = normalize_body(c["body"])
            print(f"  sec{c['sec']:>2} {c['title'][:52]:52}  {len(b):5d} chars")
        return

    if not args.write:
        print("\n(use --dry or --write)")
        return

    # wipe old concept files (keep check_okf.py)
    for dirpath, _d, files in os.walk(KN):
        for f in files:
            if f.endswith(".md"):
                os.remove(os.path.join(dirpath, f))
    for d in list(os.listdir(KN)):
        p = os.path.join(KN, d)
        if os.path.isdir(p) and not os.listdir(p):
            os.rmdir(p)

    by_sec = {}
    for c in concepts:
        by_sec.setdefault(c["sec"], []).append(c)

    root_lines = ['---', 'okf_version: "0.1"', '---', '',
                  '# Altostrat Singapore Employee Policy Handbook & Conduct Guidelines',
                  '',
                  'Open Knowledge Format (OKF v0.1) organization of the handbook. Every concept '
                  'file is the handbook\'s own text for one subsection, verbatim.', '']
    for sec_n in sorted(by_sec):
        title = sections.get(sec_n, f"Section {sec_n}")
        d = f"{sec_n:02d}-{slug(title)}"
        os.makedirs(os.path.join(KN, d), exist_ok=True)
        idx = [f"# Section {sec_n}: {title}", ""]
        root_lines.append(f"## Section {sec_n}: {title}")
        for c in by_sec[sec_n]:
            fn = f"{c['sec']}.{c['sub']}-{slug(c['title'].split(' ',1)[1])}.md"
            cid = f"{d}/{fn[:-3]}"
            body = normalize_body(c["body"])
            fm = ["---", "type: HR Policy",
                  f'title: "{c["title"]}"',
                  f'source: "Altostrat Singapore Employee Policy Handbook & Conduct Guidelines, Section {c["sec"]}.{c["sub"]}"',
                  "---", "", f"# {c['title']}", "", body, ""]
            with open(os.path.join(KN, d, fn), "w") as fh:
                fh.write("\n".join(fm))
            idx.append(f"- [{c['title']}](/{cid}.md)")
            root_lines.append(f"- [{c['title']}](/{cid}.md)")
        with open(os.path.join(KN, d, "index.md"), "w") as fh:
            fh.write("\n".join(idx) + "\n")
        root_lines.append("")
    with open(os.path.join(KN, "index.md"), "w") as fh:
        fh.write("\n".join(root_lines) + "\n")
    with open(os.path.join(KN, "log.md"), "w") as fh:
        fh.write("# Change Log\n\n## 2026-07-01\n- **Creation** — Generated verbatim from the "
                 "Altostrat Singapore Employee Policy Handbook & Conduct Guidelines PDF.\n")
    print(f"\nWROTE {len(concepts)} concepts across {len(by_sec)} sections to {KN}")


if __name__ == "__main__":
    main()
