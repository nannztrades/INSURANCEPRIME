
# tools/cleanup_repo.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "src", ROOT / "tools"]
SUFFIXES = (".bak", ".disabled")

def main() -> int:
    removed = 0
    for base in TARGETS:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in SUFFIXES:
                try:
                    p.unlink()
                    removed += 1
                    print(f"removed: {p}")
                except Exception as e:
                    print(f"skip (error): {p} :: {e}")
    print(f"Done. Files removed: {removed}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
