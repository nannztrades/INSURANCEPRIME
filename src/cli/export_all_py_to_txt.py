
# src/cli/export_all_py_to_txt.py
import argparse
import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import List, Set  # <-- added

DEFAULT_EXCLUDES = {'.venv', '.git', '__pycache__', '.vscode'}
INCLUDE_EXTS = {'.py'}

def md5_of_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()

def read_file_bytes(p: Path) -> bytes:
    # Read raw bytes to guarantee hash correctness; decode separately for text output
    with p.open('rb') as f:
        return f.read()

def decode_text(b: bytes) -> str:
    # Try UTF-8 first, then fallback with replacement to avoid crashing on odd encodings
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('utf-8', errors='replace')

def should_skip_dir(dirname: str, excludes: Set[str]) -> bool:  # <-- Set[str]
    return dirname in excludes

def collect_py_files(root: Path, excludes: Set[str]) -> List[Path]:  # <-- List[Path]
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place for performance
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d, excludes)]
        for name in filenames:
            if Path(name).suffix.lower() in INCLUDE_EXTS:
                files.append(Path(dirpath) / name)
    return sorted(files)

def format_header(rel_path: Path, size: int, digest: str) -> str:
    return (
        "\n"
        "======================================================================\n"
        f"FILE: {rel_path.as_posix()}\n"
        f"SIZE: {size} bytes | MD5: {digest}\n"
        "======================================================================\n"
    )

def add_line_numbers(text: str) -> str:
    lines = text.splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{str(i+1).rjust(width)} | {line}" for i, line in enumerate(lines))

def main():
    parser = argparse.ArgumentParser(
        description="Export the full source of every .py under a project to a single TXT (and optionally per-file TXTs)."
    )
    parser.add_argument(
        "--root", type=str, default=None,
        help="Project root to scan. Default: auto-detected (two levels up from this file)."
    )
    parser.add_argument(
        "--per-file", action="store_true",
        help="Also create one .txt per .py under exports/by_file/."
    )
    parser.add_argument(
        "--include-lines", action="store_true",
        help="Include line numbers in the combined output."
    )
    parser.add_argument(
        "--exclude", action="append", default=[],
        help="Extra directory name(s) to exclude (repeat flag to add multiple)."
    )

    args = parser.parse_args()

    # Auto-detect project root: src/cli -> src -> project root
    default_root = Path(__file__).resolve().parents[2]
    root = Path(args.root).resolve() if args.root else default_root

    # Build excludes
    excludes: Set[str] = set(DEFAULT_EXCLUDES)
    excludes.update(set(args.exclude or []))

    # Prepare export folders
    exports_dir = root / "exports"
    by_file_dir = exports_dir / "by_file"
    exports_dir.mkdir(exist_ok=True)
    if args.per_file:
        by_file_dir.mkdir(parents=True, exist_ok=True)

    # Collect files
    py_files = collect_py_files(root, excludes)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_out = exports_dir / f"ALL_PY_SOURCES_{ts}.txt"

    # Write combined
    total_bytes = 0
    with combined_out.open("w", encoding="utf-8") as out:
        header = f"Project Python sources export — {root}\nGenerated: {datetime.now().isoformat()}\n"
        out.write(header)
        out.write("-" * len(header) + "\n")

        for p in py_files:
            rel = p.relative_to(root)
            raw = read_file_bytes(p)
            text = decode_text(raw)
            digest = md5_of_bytes(raw)
            size = len(raw)
            total_bytes += size

            out.write(format_header(rel, size, digest))
            out.write(add_line_numbers(text) if args.include_lines else text)
            out.write("\n")  # trailing newline per file

            # Optional per-file export
            if args.per_file:
                target = by_file_dir / f"{rel.as_posix().replace('/', '__')}.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("w", encoding="utf-8") as tf:
                    tf.write(format_header(rel, size, digest))
                    tf.write(add_line_numbers(text) if args.include_lines else text)
                    tf.write("\n")

    print(f"Scanned {len(py_files)} Python files under: {root}")
    print(f"Excluded dirs: {sorted(excludes)}")
    print(f"Combined export written to: {combined_out}")
    if args.per_file:
        print(f"Per-file exports written under: {by_file_dir}")
    print(f"Total bytes aggregated: {total_bytes:,}")

if __name__ == "__main__":
    main()
