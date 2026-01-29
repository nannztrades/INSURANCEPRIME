
# tools/final_local_repair.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
final_local_repair.py
- Scans the repository for legacy month parsing/sorting patterns and rewrites them to canonical YYYY-MM logic.
- Creates a once-off .bak backup per changed file.
- Targets .py, .sql, .js, .html files.

Repairs include:
  1) STR_TO_DATE(CONCAT('01 ', <expr>), '%d %b %Y')    -> STR_TO_DATE(CONCAT(<expr>,'-01'), '%Y-%m-%d')
     (also handles '%%d %%b %%Y' and '%d %M %Y' and escaped variants inside Python strings)
  2) ORDER BY STR_TO_DATE(CONCAT('01 ', <expr>), '%d %b %Y') [ASC|DESC]
     -> ORDER BY STR_TO_DATE(CONCAT(<expr>,'-01'), '%Y-%m-%d') [ASC|DESC]
"""

from __future__ import annotations
import argparse
import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple

THIS = Path(__file__).resolve()
DEFAULT_ROOT = THIS.parents[1]

INCLUDE_EXTS = {".py", ".sql", ".js", ".html"}
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}

# STR_TO_DATE fixes
STR_TO_DATE_FIXES: List[Tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%d %b %Y'\s*\)",
            re.IGNORECASE,
        ),
        r"STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d')",
    ),
    (
        re.compile(
            r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%%d %%b %%Y'\s*\)",
            re.IGNORECASE,
        ),
        r"STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d')",
    ),
    (
        re.compile(
            r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%d %M %Y'\s*\)",
            re.IGNORECASE,
        ),
        r"STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d')",
    ),
    (
        re.compile(
            r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%%d %%M %%Y'\s*\)",
            re.IGNORECASE,
        ),
        r"STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d')",
    ),
]

# ORDER BY fixes
ORDER_BY_FIXES: List[Tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%d %b %Y'\s*\)\s+(ASC|DESC)",
            re.IGNORECASE,
        ),
        r"ORDER BY STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d') \2",
    ),
    (
        re.compile(
            r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%%d %%b %%Y'\s*\)\s+(ASC|DESC)",
            re.IGNORECASE,
        ),
        r"ORDER BY STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d') \2",
    ),
    (
        re.compile(
            r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%d %M %Y'\s*\)\s+(ASC|DESC)",
            re.IGNORECASE,
        ),
        r"ORDER BY STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d') \2",
    ),
    (
        re.compile(
            r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%%d %%M %%Y'\s*\)\s+(ASC|DESC)",
            re.IGNORECASE,
        ),
        r"ORDER BY STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d') \2",
    ),
]

ALL_FIXES: List[Tuple[re.Pattern, str]] = STR_TO_DATE_FIXES + ORDER_BY_FIXES

def should_skip_dir(dirname: str) -> bool:
    base = os.path.basename(dirname)
    return base in EXCLUDE_DIRS

def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(os.path.join(dirpath, d))]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in INCLUDE_EXTS:
                yield p

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")

def backup_once(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(read_text(p), encoding="utf-8")

def apply_fixes(text: str) -> Tuple[str, int]:
    changes = 0
    new = text
    for pat, repl in ALL_FIXES:
        new2, n = pat.subn(repl, new)
        if n:
            changes += n
            new = new2
    return new, changes

def repair_tree(root: Path, dry_run: bool = False) -> Tuple[int, int]:
    files_changed = 0
    total_replacements = 0
    for p in iter_files(root):
        original = read_text(p)
        fixed, n = apply_fixes(original)
        if n > 0 and fixed != original:
            if not dry_run:
                backup_once(p)
                write_text(p, fixed)
            files_changed += 1
            total_replacements += n
    return files_changed, total_replacements

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Repair legacy month parsing/sorting patterns to YYYY-MM canonical forms.")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Project root (defaults to repo root)")
    ap.add_argument("--dry-run", action="store_true", help="Scan and report without writing changes")
    return ap.parse_args()

def main() -> int:
    args = parse_args()
    root: Path = args.root.resolve()
    if not root.exists():
        print(f"[repair] Root not found: {root}")
        return 2
    print(f"[repair] Scanning under: {root}")
    print(f"[repair] Dry-run: {'YES' if args.dry_run else 'NO'}")
    files_changed, total_replacements = repair_tree(root, dry_run=args.dry_run)
    print(f"[repair] Files changed: {files_changed}")
    print(f"[repair] Total replacements: {total_replacements}")
    if args.dry_run:
        print("[repair] No files were modified (dry-run).")
    else:
        print("[repair] Backups (.bak) created once per file as needed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
