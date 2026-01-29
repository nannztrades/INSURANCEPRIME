
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_month_year_normalisation.py

Normalises inbound `month_year` on all agent-facing routes by inserting:

    if month_year is not None:
        month_year = normalize_month_param(month_year)

Targets:
- src/api/agent_api.py
- src/api/agent_reports.py
- src/api/agent_missing.py

Idempotent; writes <file>.bak on first change.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---- repo layout -------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
TARGETS = [
    SRC / "api" / "agent_api.py",
    SRC / "api" / "agent_reports.py",
    SRC / "api" / "agent_missing.py",
]

# ---- code we insert / ensure -------------------------------------------------
IMPORT_LINE = "from src.util.periods import normalize_month_param"
SNIPPET_LINES = [
    "# -- normalize month_year to canonical YYYY-MM --",
    "if month_year is not None:",
    "    month_year = normalize_month_param(month_year)",
]

# function def that has a parameter named month_year (robust to annotations/defaults)
DEF_RE = re.compile(
    r"^def\s+\w+\s*\((?P<params>[^)]*\bmonth_year\b[^)]*)\):",
    re.MULTILINE,
)

# docstring opener: optional prefixes r/f/u/fr/rf/ur/ru + triple quotes
DOCSTRING_OPEN_RE = re.compile(
    r'^\s*(?:r|u|f|fr|rf|ur|ru)?("""|\'\'\')',
    re.IGNORECASE,
)

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")

def backup_once(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(read(p), encoding="utf-8")

def ensure_import(txt: str) -> str:
    """Insert the IMPORT_LINE after the last top-level import if missing."""
    if IMPORT_LINE in txt:
        return txt
    lines = txt.splitlines(True)
    last_imp = -1
    for i, line in enumerate(lines[:300]):  # imports typically near top
        s = line.lstrip()
        if s.startswith("from ") or s.startswith("import "):
            last_imp = i
        if s.startswith("def ") or s.startswith("class "):
            break
    insert_at = last_imp + 1 if last_imp >= 0 else 0
    lines.insert(insert_at, IMPORT_LINE + "\n")
    return "".join(lines)

def _next_nonblank_line(text: str, start: int) -> tuple[int, str]:
    """Return (line_start_index, line_text) of next non-blank line or (len, '')."""
    i = start
    n = len(text)
    while i < n:
        j = text.find("\n", i)
        if j == -1:
            j = n
        line = text[i:j]
        if line.strip():
            return i, line
        i = j + 1
    return n, ""

def _line_indent(s: str) -> str:
    return s[:len(s) - len(s.lstrip(" "))]

def _find_docstring_block(text: str, line_start: int, opener: str) -> int:
    """
    Given index of a line that starts with a docstring opener, return the index
    just AFTER the end-of-line of the closing triple quotes.
    If not found, return the end-of-text (best-effort).
    """
    i = text.find("\n", line_start)
    if i == -1:
        i = len(text)
    end_pos = text.find(opener, i)
    if end_pos == -1:
        return len(text)
    eol = text.find("\n", end_pos + len(opener))
    if eol == -1:
        eol = len(text)
    return eol + 1

def _function_already_normalized(chunk: str) -> bool:
    return "normalize_month_param(month_year)" in chunk

def insert_normalization(txt: str) -> str:
    """
    For each function that has a `month_year` parameter, insert the normalization
    snippet right after the header and possible docstring.
    """
    out = []
    i = 0
    while True:
        m = DEF_RE.search(txt, i)
        if not m:
            out.append(txt[i:])
            break

        header_end = txt.find("\n", m.end())
        if header_end == -1:
            out.append(txt[i:])
            break

        out.append(txt[i:header_end + 1])

        probe_chunk = txt[header_end + 1: header_end + 1 + 1024]
        if _function_already_normalized(probe_chunk):
            i = header_end + 1
            continue

        next_idx, next_line = _next_nonblank_line(txt, header_end + 1)
        body_indent = _line_indent(next_line) if next_line else "    "
        if not body_indent:
            body_indent = "    "

        doc_m = DOCSTRING_OPEN_RE.match(next_line)
        insert_at = header_end + 1
        if doc_m:
            opener = doc_m.group(1)
            insert_at = _find_docstring_block(txt, next_idx, opener)

        out.append(txt[header_end + 1:insert_at])

        snippet = (
            f"{body_indent}{SNIPPET_LINES[0]}\n"
            f"{body_indent}{SNIPPET_LINES[1]}\n"
            f"{body_indent}{SNIPPET_LINES[2]}\n"
        )

        out.append(snippet)
        i = insert_at

    return "".join(out)

def patch_file(p: Path) -> bool:
    if not p.exists():
        return False
    original = read(p)
    txt = ensure_import(original)
    txt = insert_normalization(txt)
    if txt != original:
        backup_once(p)
        write(p, txt)
        return True
    return False

def main() -> int:
    changed = 0
    for t in TARGETS:
        try:
            if patch_file(t):
                changed += 1
                print(f"[patch] updated: {t.relative_to(REPO)}")
            else:
                print(f"[patch] no changes: {t.relative_to(REPO)}")
        except Exception as e:
            print(f"[patch] ERROR processing {t}: {e}")
    print(f"[patch] files changed: {changed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
