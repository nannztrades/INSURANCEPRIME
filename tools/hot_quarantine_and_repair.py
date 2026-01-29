
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hot_quarantine_and_repair.py

Minimal, safe fixes to clear editor errors quickly:
  • Quarantine tool files that VS Code is parsing and reporting as broken.
  • Restore key modules from .bak if available; otherwise, move __future__ imports to top.
  • Remove our injected sys.path block in tests/conftest.py (so __future__ can be first).
  • Remove venv site-packages .pth (insurancelocal_src.pth).
Idempotent. Prints a summary. No project-wide rewrites.
"""

from __future__ import annotations
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
SRC = REPO / "src"
TESTS = REPO / "tests"
VENV = REPO / ".venv"

# 1) Tool files to quarantine (stop Pylance from parsing them)
TOOL_FILES = [
    "final_local_repair.py",
    "fix_import_resolution.py",
]

# 2) Files we try to restore from .bak, else gently repair
CANDIDATES_RESTORE_OR_FIX = [
    SRC / "reports" / "monthly_reports.py",
    SRC / "ingestion" / "parser_db_integration.py",
]

# 3) conftest.py markers (remove injected sys.path block)
CONFTEST = TESTS / "conftest.py"
CONFTEST_BEGIN_MARKERS = [
    "# --- auto-added: make repo/src importable in tests ---",
    "# --- auto-added for tests: make <repo>/src importable ---",
]
CONFTEST_END_MARKER = "# --- end auto-add ---"

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def quarantine_tools() -> list[tuple[str, str]]:
    out = []
    for name in TOOL_FILES:
        p = TOOLS / name
        if not p.exists():
            out.append((f"tools/{name}", "not found"))
            continue
        q = p.with_suffix(p.suffix + ".disabled")
        if q.exists():
            out.append((f"tools/{name}", f"already quarantined as {q.name}"))
            continue
        try:
            p.rename(q)
            out.append((f"tools/{name}", f"renamed to {q.name}"))
        except Exception as e:
            out.append((f"tools/{name}", f"ERROR renaming: {e}"))
    return out

def try_restore_from_bak(path: Path) -> str:
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        return "no .bak (will try soft-fix)"
    try:
        write_text(path, read_text(bak))
        return f"restored from {bak.name}"
    except Exception as e:
        return f"ERROR restoring from {bak.name}: {e}"

_FUTURE_IMPORT_RE = re.compile(r"(?m)^\s*from\s+__future__\s+import\s+[^\n]+$")

def move_future_to_top(path: Path) -> str:
    """
    If file contains `from __future__ import ...`, ensure it's the very first code line.
    Keeps encoding/shebang if present. Safe for arbitrary files.
    """
    if not path.exists():
        return "missing (skipped)"
    try:
        text = read_text(path)
        # If no future import, nothing to do
        m = _FUTURE_IMPORT_RE.search(text)
        if not m:
            return "no __future__ import (skipped)"
        # Split header lines (shebang / coding)
        lines = text.splitlines()
        header = []
        i = 0
        while i < len(lines) and (
            lines[i].startswith("#!") or
            lines[i].startswith("# -*- coding:") or
            lines[i].startswith("# coding:")
        ):
            header.append(lines[i])
            i += 1
        # Remove all future imports and gather them
        futures = _FUTURE_IMPORT_RE.findall(text)
        body_wo_future = _FUTURE_IMPORT_RE.sub("", "\n".join(lines[i:]))
        # Rebuild: header, future(s), then rest (strip leading blank lines)
        body_wo_future = body_wo_future.lstrip("\n")
        new_text = "\n".join(header + futures + ["", body_wo_future]).rstrip() + "\n"
        if new_text != text:
            write_text(path, new_text)
            return "moved __future__ import(s) to top"
        return "already correct (no changes)"
    except Exception as e:
        return f"ERROR adjusting __future__ order: {e}"

def clean_conftest_injection() -> str:
    p = CONFTEST
    if not p.exists():
        return "tests/conftest.py missing (skipped)"
    try:
        s = read_text(p)
        # find first matching begin marker
        begin = -1
        begin_marker = ""
        for m in CONFTEST_BEGIN_MARKERS:
            i = s.find(m)
            if i != -1:
                begin = i
                begin_marker = m
                break
        if begin == -1:
            return "no injected block found (skipped)"
        end = s.find(CONFTEST_END_MARKER, begin)
        if end == -1:
            end = begin + len(begin_marker)
        else:
            end += len(CONFTEST_END_MARKER)
        # Remove the block and a single trailing newline if present
        tail = s[end:]
        if tail.startswith("\n"):
            tail = tail[1:]
        new_s = s[:begin] + tail
        if new_s != s:
            write_text(p, new_s)
            return "removed injected sys.path block"
        return "no changes"
    except Exception as e:
        return f"ERROR cleaning conftest: {e}"

def remove_venv_pth() -> str:
    try:
        if not VENV.exists():
            return ".venv not found (skipped)"
        for sp in VENV.rglob("site-packages"):
            pth = sp / "insurancelocal_src.pth"
            if pth.exists():
                pth.unlink()
                return f"deleted {pth}"
        return "no .pth found (skipped)"
    except Exception as e:
        return f"ERROR removing .pth: {e}"

def main() -> int:
    results: list[tuple[str, str]] = []

    # 1) Quarantine noisy tool files
    for name, status in quarantine_tools():
        results.append((name, status))

    # 2) conftest.py – remove injected block (so __future__ can be first)
    results.append(("tests/conftest.py", clean_conftest_injection()))

    # 3) Restore or soft-fix core Python modules
    for path in CANDIDATES_RESTORE_OR_FIX:
        status = try_restore_from_bak(path)
        results.append((str(path.relative_to(REPO)), status))
        if "no .bak" in status:
            results.append((str(path.relative_to(REPO)), move_future_to_top(path)))

    # 4) Remove venv site-packages .pth
    results.append(("venv .pth", remove_venv_pth()))

    print("\n[hot-fix] Summary")
    for pat, st in results:
        print(f"[hot-fix] {pat}: {st}")
    print("\n[hot-fix] Done. In VS Code: Command Palette → Developer: Reload Window.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
