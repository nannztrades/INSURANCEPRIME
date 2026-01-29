import hashlib
import os
from pathlib import Path
from datetime import datetime
from typing import List, Set

# Root of the project to scan
PROJECT_ROOT = Path(r"D:\PROJECT\INSURANCELOCAL")

# Exclusions (directory names only, not full paths)
EXCLUDES_DIR: Set[str] = {'.git', '.venv', '__pycache__', '.vscode'}
EXCLUDES_FILE: Set[str] = {'Thumbs.db'}
INCLUDE_EXTS = {'.py'}


# -------------------------
# Helpers: size formatting
# -------------------------
def fmt_size(n: int) -> str:
    """Return a human-readable file size string like '10 KB'."""
    size = float(n)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.0f} {unit}"
        size /= 1024.0
    return f"{size:.0f} PB"


# -------------------------
# Helpers: project tree
# -------------------------
def print_tree_to_lines(root: Path) -> List[str]:
    """
    Build a tree representation of the directory structure starting at root.
    Returns a list of lines (strings). Does not print to stdout.
    """

    lines: List[str] = []

    def _print_tree(current: Path, prefix: str = "") -> None:
        entries = []
        for p in sorted(current.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
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
                lines.append(line)
                extension = "    " if is_last else "│   "
                _print_tree(p, prefix + extension)
            else:
                try:
                    stat = p.stat()
                    size_str = fmt_size(stat.st_size)
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    line = f"{prefix}{connector}{p.name}    [{size_str} | {mtime}]"
                except OSError:
                    # Fallback if stat fails for some reason
                    line = f"{prefix}{connector}{p.name}"
                lines.append(line)

    header = f"Project tree for: {root}"
    underline = "-" * len(header)
    lines.append(header)
    lines.append(underline)
    _print_tree(root)
    lines.append("")  # blank line after tree
    return lines


# -------------------------
# Helpers: file reading & hashing
# -------------------------
def md5_of_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def read_file_bytes(p: Path) -> bytes:
    with p.open('rb') as f:
        return f.read()


def decode_text(b: bytes) -> str:
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('utf-8', errors='replace')


# -------------------------
# Helpers: file collection
# -------------------------
def should_skip_dir(dirname: str, excludes: Set[str]) -> bool:
    return dirname in excludes


def collect_py_files(root: Path, excludes: Set[str]) -> List[Path]:
    files: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d, excludes)]
        for name in filenames:
            if Path(name).suffix.lower() in INCLUDE_EXTS:
                files.append(Path(dirpath) / name)
    return sorted(files)


# -------------------------
# Helpers: formatting
# -------------------------
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
    return "\n".join(f"{str(i + 1).rjust(width)} | {line}" for i, line in enumerate(lines))


# -------------------------
# Main routine
# -------------------------
def main() -> None:
    root = PROJECT_ROOT

    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Project root does not exist or is not a directory: {root}")

    # Prepare export folder
    exports_dir = root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_out = exports_dir / f"ALL_PY_SOURCES_{ts}.txt"

    # Collect tree lines
    tree_lines = print_tree_to_lines(root)

    # Collect .py files
    excludes: Set[str] = set(EXCLUDES_DIR)
    py_files = collect_py_files(root, excludes)

    total_bytes = 0

    with combined_out.open("w", encoding="utf-8") as out:
        # Write project tree first
        for line in tree_lines:
            out.write(line + "\n")

        # Extra separator between tree and sources section
        out.write("\n\n")
        out.write("########## PYTHON SOURCES ##########\n")
        out.write("\n")

        for p in py_files:
            rel = p.relative_to(root)
            raw = read_file_bytes(p)
            text = decode_text(raw)
            digest = md5_of_bytes(raw)
            size = len(raw)
            total_bytes += size

            out.write(format_header(rel, size, digest))
            # If you don't want line numbers, change the next line to: out.write(text)
            out.write(add_line_numbers(text))
            out.write("\n")  # trailing newline per file

    print(f"Scanned {len(py_files)} Python files under: {root}")
    print(f"Excluded dirs: {sorted(excludes)}")
    print(f"Combined export (tree + sources) written to: {combined_out}")
    print(f"Total bytes aggregated from .py files: {total_bytes:,}")


if __name__ == "__main__":
    main()