
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
revert_final_local_repair.py

Rolls back changes made by "final_local_repair.py" (and earlier helper scripts) by:
  - Restoring files from their .bak backups if present
  - Removing our sys.path injection block in tests/conftest.py if no backup exists
  - Deleting the venv site-packages .pth we created (insurancelocal_src.pth)
  - Deleting src/util/periods.py and src/util/__init__.py only if they match the generated content
  - Printing a detailed summary of actions taken

Safe to run multiple times. Exits with code 0 even if some items were already clean.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
TESTS = REPO / "tests"
VSCODE = REPO / ".vscode"
VENV = REPO / ".venv"

# Primary targets we may have modified
TARGETS = [
    SRC / "ingestion" / "parser_db_integration.py",
    SRC / "reports" / "monthly_reports.py",
    TESTS / "conftest.py",
    SRC / "api" / "agent_api.py",
    SRC / "api" / "agent_reports.py",
    SRC / "api" / "agent_missing.py",
    VSCODE / "settings.json",
    REPO / "pyrightconfig.json",
]

# venv .pth created by our script
PTH_NAME = "insurancelocal_src.pth"

# Our util package files (only delete if they match our auto-generated contents)
UTIL_INIT = SRC / "util" / "__init__.py"
UTIL_PERIODS = SRC / "util" / "periods.py"

# ---------------------------------------------------------------------------
# Content signatures to detect "our" files safely
# ---------------------------------------------------------------------------
UTIL_INIT_EXPECTED = "__all__ = []\n"

UTIL_PERIODS_EXPECTED = """\
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# Patterns
_RE_CANONICAL = re.compile(r"^\\d{4}-(0[1-9]|1[0-2])$")         # YYYY-MM
_RE_YEAR_DASH_M = re.compile(r"^(\\d{4})-(\\d{1,2})$")          # YYYY-M
_RE_YEAR_SLASH_MM = re.compile(r"^(\\d{4})/(0[1-9]|1[0-2])$")   # YYYY/MM
_RE_COM_PREFIX = re.compile(r"^COM_", re.IGNORECASE)

_MONTH_FMTS = ("%b %Y", "%B %Y")  # e.g., "Jun 2025", "June 2025"

def normalize_month_param(raw: Optional[str]) -> Optional[str]:
    \"\"\"Convert various month inputs to canonical 'YYYY-MM'. Returns None if invalid.\"\"\"
    if not raw:
        return None

    s = raw.strip()
    if not s:
        return None

    # Drop COM_ prefix if present
    s = _RE_COM_PREFIX.sub("", s)

    # Already canonical
    if _RE_CANONICAL.fullmatch(s):
        return s

    # YYYY-M  -> YYYY-MM
    m = _RE_YEAR_DASH_M.fullmatch(s)
    if m:
        year = int(m.group(1))
        mm = int(m.group(2))
        if 1 <= mm <= 12:
            return f"{year:04d}-{mm:02d}"

    # YYYY/MM -> YYYY-MM
    m = _RE_YEAR_SLASH_MM.fullmatch(s)
    if m:
        return f"{int(m.group(1)):04d}-{m.group(2)}"

    # Month name + year
    for fmt in _MONTH_FMTS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m")
        except ValueError:
            pass

    return None
"""

# Markers of our sys.path injection in tests/conftest.py
CONFTEST_BEGIN_MARKERS = [
    "# --- auto-added: make repo/src importable in tests ---",
    "# --- auto-added for tests: make <repo>/src importable ---",
]
CONFTEST_END_MARKER = "# --- end auto-add ---"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def restore_from_bak(p: Path) -> str:
    """If p.bak exists, restore p from it (overwrite p's contents)."""
    bak = p.with_suffix(p.suffix + ".bak")
    if bak.exists():
        try:
            original = read_text(bak)
            write_text(p, original)
            return f"restored from {bak.name}"
        except Exception as e:
            return f"ERROR restoring from {bak.name}: {e}"
    return "no .bak (skipped)"

def try_remove_conftest_injection(p: Path) -> str:
    """If no .bak exists, remove our injected sys.path block by markers."""
    if not p.exists():
        return "conftest.py missing (skipped)"
    bak = p.with_suffix(p.suffix + ".bak")
    if bak.exists():
        return "backup exists; not editing (already restored above or will be)"
    try:
        txt = read_text(p)
        # Find the first matching begin marker
        begin_pos = -1
        used_marker = ""
        for m in CONFTEST_BEGIN_MARKERS:
            tmp = txt.find(m)
            if tmp != -1:
                begin_pos = tmp
                used_marker = m
                break
        if begin_pos == -1:
            return "no injected block found (skipped)"

        end_pos = txt.find(CONFTEST_END_MARKER, begin_pos)
        if end_pos == -1:
            # If end marker missing, remove from begin marker to a couple of lines later as best-effort
            end_pos = begin_pos + len(used_marker)
        else:
            end_pos += len(CONFTEST_END_MARKER)

        # Also trim possible trailing newline after the block
        tail = txt[end_pos:]
        tail = tail[1:] if tail.startswith("\n") else tail

        new_txt = txt[:begin_pos] + tail
        if new_txt != txt:
            write_text(p, new_txt)
            return "removed injected sys.path block"
        return "no changes"
    except Exception as e:
        return f"ERROR cleaning injected block: {e}"

def maybe_delete_generated_file(path: Path, expected: str) -> str:
    """Delete file only if it matches our auto-generated content exactly."""
    if not path.exists():
        return "missing (skipped)"
    try:
        if read_text(path) == expected:
            path.unlink()
            return "deleted (matched generated content)"
        return "kept (content differs)"
    except Exception as e:
        return f"ERROR reading/deleting: {e}"

def remove_venv_pth(venv_dir: Path) -> str:
    if not venv_dir.exists():
        return ".venv not found (skipped)"
    try:
        for sp in venv_dir.rglob("site-packages"):
            pth = sp / PTH_NAME
            if pth.exists():
                pth.unlink()
                return f"deleted {pth}"
        return "no .pth found (skipped)"
    except Exception as e:
        return f"ERROR removing .pth: {e}"

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    results: list[tuple[str, str]] = []

    # 1) Restore primary targets from .bak
    for p in TARGETS:
        if p.exists() or p.with_suffix(p.suffix + ".bak").exists():
            status = restore_from_bak(p)
            results.append((str(p.relative_to(REPO)), status))

    # 2) If conftest has no .bak, remove our injected block
    conf = TESTS / "conftest.py"
    if conf.exists():
        status = try_remove_conftest_injection(conf)
        results.append((str(conf.relative_to(REPO)), status))

    # 3) Remove the venv site-packages .pth
    results.append(("venv .pth", remove_venv_pth(VENV)))

    # 4) Remove util files only if they match our generated content
    results.append((str(UTIL_INIT.relative_to(REPO)), maybe_delete_generated_file(UTIL_INIT, UTIL_INIT_EXPECTED)))
    results.append((str(UTIL_PERIODS.relative_to(REPO)), maybe_delete_generated_file(UTIL_PERIODS, UTIL_PERIODS_EXPECTED)))

    # 5) Print summary
    print("\n[revert] Summary")
    for target, status in results:
        print(f"[revert] {target}: {status}")

    print("\n[revert] Done. You can now reload VS Code (Developer: Reload Window).")
    print("If pytest still fails, please run it and share the new trace; we’ll surgically fix only what’s needed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
