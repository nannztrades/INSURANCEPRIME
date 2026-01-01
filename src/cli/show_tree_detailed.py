
# src/cli/show_tree_detailed.py
import os
from pathlib import Path
from datetime import datetime

EXCLUDES_DIR = {'.git', '.venv', '__pycache__'}
EXCLUDES_FILE = {'Thumbs.db'}

def fmt_size(n: int) -> str:
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024.0:
            return f"{n:.0f} {unit}"
        n /= 1024.0
    return f"{n:.0f} PB"

def print_tree(root: Path, prefix: str = "", lines = None):
    entries = []
    for p in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        name = p.name
        if p.is_dir() and name in EXCLUDES_DIR:
            continue
        if p.is_file() and name in EXCLUDES_FILE:
            continue
        entries.append(p)

    count = len(entries)
    for i, p in enumerate(entries):
        is_last = (i == count - 1)
        connector = "└── " if is_last else "├── "
        if p.is_dir():
            line = f"{prefix}{connector}{p.name}/"
            print(line)
            if lines is not None: lines.append(line)
            extension = "    " if is_last else "│   "
            print_tree(p, prefix + extension, lines)
        else:
            size = fmt_size(p.stat().st_size)
            mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            line = f"{prefix}{connector}{p.name}    [{size} | {mtime}]"
            print(line)
            if lines is not None: lines.append(line)

def main():
    # Go up two levels from this file to project root (src/cli -> src -> root)
    root = Path(__file__).resolve().parents[2]
    header = f"Project tree for: {root}"
    print(header)
    print("-" * len(header))
    lines = [header, "-" * len(header)]
    print_tree(root, lines=lines)

    # Save alongside project root for alignment
    out = root / "project_tree_detailed.txt"
    with out.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    print(f"\nSaved a copy to: {out}")

if __name__ == "__main__":
    main()
