
# src/cli/show_tree.py
import os
from pathlib import Path

EXCLUDES_DIR = {'.git', '.venv', '__pycache__'}
EXCLUDES_FILE = {'Thumbs.db'}

def print_tree(root: Path, prefix: str = ""):
    # Gather entries
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
        print(prefix + connector + p.name)
        if p.is_dir():
            extension = "    " if is_last else "│   "
            print_tree(p, prefix + extension)

def main():
    root = Path(__file__).resolve().parents[2]  # go up from src/cli to project root
    print(f"Project tree for: {root}\n")
    print_tree(root)

    # Also write to file for sharing/reference
    out = root / "project_tree.txt"
    with out.open("w", encoding="utf-8") as f:
        # Capture the same output
        def write_tree(r: Path, prefix: str = ""):
            entries = []
            for p in sorted(r.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
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
                f.write(prefix + connector + p.name + "\n")
                if p.is_dir():
                    extension = "    " if is_last else "│   "
                    write_tree(p, prefix + extension)
        write_tree(root)
    print(f"\nSaved to {out}")

if __name__ == "__main__":
    main()
