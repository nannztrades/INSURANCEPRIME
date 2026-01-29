#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combine multiple .py files from a chosen folder (recursively) into one big TXT,
with a GUI to pick input/output folders and select which files to include.

Features:
- Choose input and output folders
- Scan recursively for .py files
- Filter box to narrow list
- Select all/none/invert
- Combine ALL or only SELECTED scripts to a single .txt
- Robust encoding detection (utf-8, utf-8-sig, cp1252, latin-1; fallback with replacement)
- Optional exclude common folders (.git, .venv, __pycache__, build, dist)
- Sort by path or size
- Progress bar and summary

No external dependencies. Uses Tkinter (standard library).
Tested on Windows/macOS/Linux with Python 3.8+.
"""

import os
import sys
import traceback
import time
import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

APP_TITLE = "Combine Python Scripts → One TXT"
DEFAULT_OUTPUT_BASENAME = "combined_python_scripts"
SEPARATOR_LINE = "#" * 80

DEFAULT_EXCLUDES = {".git", ".venv", "__pycache__", "build", "dist"}

def human_size(n: int) -> str:
    """Return human-readable file size."""
    for unit in ["bytes", "KB", "MB", "GB"]:
        if n < 1024.0:
            return f"{n:,.0f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"

def open_folder(path: str):
    """Open folder in OS file manager."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass  # non-fatal

class CombineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(980, 640)
        self.files = []  # list of dicts: {"path": Path, "rel": str, "size": int}
        self.filtered_indices = []  # mapping of visible listbox rows -> files indices
        self.input_dir = None
        self.output_dir = None
        self._make_widgets()

    # ---------------------- UI LAYOUT ----------------------
    def _make_widgets(self):
        self.columnconfigure(0, weight=1)

        # Top: path selection
        paths_frame = ttk.LabelFrame(self, text="Folders")
        paths_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        for c in range(3):
            paths_frame.columnconfigure(c, weight=(1 if c == 1 else 0))

        ttk.Label(paths_frame, text="Input Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.in_entry = ttk.Entry(paths_frame)
        self.in_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse…", command=self.choose_input).grid(row=0, column=2, sticky="e", padx=5, pady=5)

        ttk.Label(paths_frame, text="Output Folder:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.out_entry = ttk.Entry(paths_frame)
        self.out_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(paths_frame, text="Browse…", command=self.choose_output).grid(row=1, column=2, sticky="e", padx=5, pady=5)

        # Options row: excludes + sort + scan
        options = ttk.Frame(paths_frame)
        options.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=(2,8))
        options.columnconfigure(6, weight=1)

        self.exclude_var = tk.BooleanVar(value=True)
        self.exclude_chk = ttk.Checkbutton(options, text="Exclude common folders (.git, .venv, __pycache__, build, dist)", variable=self.exclude_var)
        self.exclude_chk.grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Label(options, text="Sort by:").grid(row=0, column=4, sticky="e", padx=(15, 4))
        self.sort_var = tk.StringVar(value="path")
        self.sort_combo = ttk.Combobox(options, state="readonly", textvariable=self.sort_var, values=["path", "size"])
        self.sort_combo.grid(row=0, column=5, sticky="w", padx=(0, 12))
        self.sort_combo.bind("<<ComboboxSelected>>", lambda e: self.sort_and_refresh())

        self.scan_btn = ttk.Button(options, text="Scan for .py files", command=self.scan)
        self.scan_btn.grid(row=0, column=7, sticky="e")

        # Middle: filter + list
        mid_frame = ttk.Frame(self)
        mid_frame.grid(row=1, column=0, sticky="nsew", padx=10)
        mid_frame.columnconfigure(0, weight=1)
        mid_frame.rowconfigure(2, weight=1)

        # Stats + Filter
        top_tools = ttk.Frame(mid_frame)
        top_tools.grid(row=0, column=0, sticky="ew", pady=(0,5))
        top_tools.columnconfigure(2, weight=1)

        self.stats_label = ttk.Label(top_tools, text="No files scanned.")
        self.stats_label.grid(row=0, column=0, sticky="w", padx=(0,10))

        ttk.Label(top_tools, text="Filter (name/path):").grid(row=0, column=1, sticky="e")
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(top_tools, textvariable=self.filter_var)
        self.filter_entry.grid(row=0, column=2, sticky="ew", padx=(5,0))
        self.filter_var.trace_add("write", lambda *args: self.apply_filter())

        # Listbox + scrollbar
        list_frame = ttk.Frame(mid_frame)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame, selectmode=tk.EXTENDED, activestyle="dotbox", exportselection=False
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.config(yscrollcommand=self.scrollbar.set)

        # Selection tools
        sel_frame = ttk.Frame(mid_frame)
        sel_frame.grid(row=3, column=0, sticky="ew", pady=5)
        ttk.Button(sel_frame, text="Select All", command=self.select_all).grid(row=0, column=0, padx=2)
        ttk.Button(sel_frame, text="Select None", command=self.select_none).grid(row=0, column=1, padx=2)
        ttk.Button(sel_frame, text="Invert Selection", command=self.invert_selection).grid(row=0, column=2, padx=2)

        # Actions
        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        actions.columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(actions, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        btns = ttk.Frame(actions)
        btns.grid(row=1, column=0, sticky="e")
        self.combine_all_btn = ttk.Button(btns, text="Combine ALL → TXT", command=lambda: self.combine(save_all=True))
        self.combine_sel_btn = ttk.Button(btns, text="Combine Selected → TXT", command=lambda: self.combine(save_all=False))
        self.combine_all_btn.grid(row=0, column=0, padx=5)
        self.combine_sel_btn.grid(row=0, column=1, padx=5)

        # Status
        self.status = ttk.Label(self, text="Ready.", anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", padx=10, pady=(0,10))

        # Configure resizing
        self.rowconfigure(1, weight=1)

    # ---------------------- PATH PICKERS ----------------------
    def choose_input(self):
        d = filedialog.askdirectory(title="Choose input folder")
        if d:
            self.input_dir = Path(d)
            self.in_entry.delete(0, tk.END)
            self.in_entry.insert(0, str(self.input_dir))

    def choose_output(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.output_dir = Path(d)
            self.out_entry.delete(0, tk.END)
            self.out_entry.insert(0, str(self.output_dir))

    # ---------------------- SCANNING ----------------------
    def scan(self):
        self.input_dir = Path(self.in_entry.get().strip() or "")
        if not self.input_dir or not self.input_dir.exists() or not self.input_dir.is_dir():
            messagebox.showwarning("Input Required", "Please choose a valid input folder.")
            return

        self.status.config(text="Scanning…")
        self.update_idletasks()

        found = []
        base = self.input_dir.resolve()

        excludes = set(DEFAULT_EXCLUDES) if self.exclude_var.get() else set()

        for root, dirs, files in os.walk(base):
            # prune excluded dirs
            if excludes:
                dirs[:] = [d for d in dirs if d not in excludes]
            for fname in files:
                if fname.lower().endswith(".py"):
                    p = Path(root) / fname
                    try:
                        size = p.stat().st_size
                    except OSError:
                        size = 0
                    try:
                        rel = str(p.resolve().relative_to(base))
                    except Exception:
                        rel = str(p.name)
                    found.append({"path": p.resolve(), "rel": rel, "size": size})

        self.files = self._sort_files(found)
        self.populate_list(self.files)
        self.status.config(text=f"Scan complete. Found {len(self.files)} .py files.")

    def _sort_files(self, filelist):
        if self.sort_var.get() == "size":
            return sorted(filelist, key=lambda d: (d["size"], d["rel"].lower()))
        return sorted(filelist, key=lambda d: d["rel"].lower())

    def sort_and_refresh(self):
        if not self.files:
            return
        self.files = self._sort_files(self.files)
        self.apply_filter()

    def populate_list(self, filelist):
        self.listbox.delete(0, tk.END)
        self.filtered_indices = list(range(len(filelist)))
        for f in filelist:
            line = f"{f['rel']} — {human_size(f['size'])}"
            self.listbox.insert(tk.END, line)
        self.stats_label.config(text=f"Total: {len(self.files)} | Showing: {len(self.filtered_indices)}")

    def apply_filter(self):
        term = (self.filter_var.get() or "").strip().lower()
        self.listbox.delete(0, tk.END)
        self.filtered_indices = []
        if not self.files:
            self.stats_label.config(text="No files scanned.")
            return

        if not term:
            self.filtered_indices = list(range(len(self.files)))
            for f in self.files:
                self.listbox.insert(tk.END, f"{f['rel']} — {human_size(f['size'])}")
        else:
            for i, f in enumerate(self.files):
                hay = f"{f['rel']} {str(f['path'])}".lower()
                if term in hay:
                    self.filtered_indices.append(i)
                    self.listbox.insert(tk.END, f"{f['rel']} — {human_size(f['size'])}")

        self.stats_label.config(text=f"Total: {len(self.files)} | Showing: {len(self.filtered_indices)}")

    # ---------------------- SELECTION HELPERS ----------------------
    def select_all(self):
        self.listbox.select_set(0, tk.END)

    def select_none(self):
        self.listbox.select_clear(0, tk.END)

    def invert_selection(self):
        current = set(self.listbox.curselection())
        self.listbox.select_set(0, tk.END)
        for i in range(self.listbox.size()):
            if i in current:
                self.listbox.select_clear(i)

    # ---------------------- COMBINE ----------------------
    def combine(self, save_all: bool):
        if not self.files:
            messagebox.showinfo("No Files", "Please scan for .py files first.")
            return

        # Output folder validation
        self.output_dir = Path(self.out_entry.get().strip() or "")
        if not self.output_dir or not self.output_dir.exists() or not self.output_dir.is_dir():
            messagebox.showwarning("Output Required", "Please choose a valid output folder.")
            return

        # Determine which indices to include
        if save_all:
            include_indices = list(range(len(self.files)))
        else:
            selections = self.listbox.curselection()
            if not selections:
                messagebox.showinfo("No Selection", "Please select at least one file, or use 'Combine ALL'.")
                return
            include_indices = [self.filtered_indices[i] for i in selections]  # map visible rows to actual indices

        # Ask for optional custom filename
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{DEFAULT_OUTPUT_BASENAME}_{ts}.txt"
        out_path = self.output_dir / default_name

        # Allow the user to override (within output folder)
        answer = messagebox.askyesno("Filename", f"Use default filename?\n\n{default_name}")
        if not answer:
            # Ask user to enter a filename (no dialogs outside output folder to match your request)
            name = simpledialog.askstring("Filename", "Enter a filename (without path):", initialvalue=default_name)
            if not name:
                return
            name = name.strip()
            if not name.lower().endswith(".txt"):
                name += ".txt"
            out_path = self.output_dir / name

        # Combine
        total = len(include_indices)
        self.progress.config(maximum=total, value=0)
        self.status.config(text="Combining…")
        self.update_idletasks()

        errors = []
        files_written = 0
        start_time = time.time()

        try:
            with open(out_path, "w", encoding="utf-8", newline="\n") as out:
                header = (
                    f"{SEPARATOR_LINE}\n"
                    f"# Combined Python Scripts\n"
                    f"# Created: {datetime.datetime.now().isoformat(timespec='seconds')}\n"
                    f"# Source base: {self.input_dir}\n"
                    f"# Files included: {total}\n"
                    f"{SEPARATOR_LINE}\n\n"
                )
                out.write(header)

                for i, idx in enumerate(include_indices, start=1):
                    f = self.files[idx]
                    path = f["path"]
                    rel = f["rel"]
                    size = f["size"]

                    # Read file with robust encoding fallback
                    content = None
                    used_encoding = None
                    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
                        try:
                            with open(path, "r", encoding=enc, errors="strict") as fh:
                                content = fh.read()
                                used_encoding = enc
                                break
                        except Exception:
                            continue
                    if content is None:
                        # last resort with errors=replace so we never fail write
                        try:
                            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                                content = fh.read()
                                used_encoding = "utf-8 (errors=replace)"
                        except Exception as e:
                            errors.append(f"READ FAIL: {path} :: {e}")
                            continue

                    # Write section
                    section_header = (
                        f"{SEPARATOR_LINE}\n"
                        f"# ===== FILE: {rel} =====\n"
                        f"# ABS: {path}\n"
                        f"# SIZE: {size:,} bytes\n"
                        f"# ENCODING: {used_encoding}\n"
                        f"# ===== START =====\n"
                    )
                    out.write(section_header)
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
                    out.write(f"# ===== END FILE: {rel} =====\n\n")
                    files_written += 1

                    self.progress.config(value=i)
                    self.status.config(text=f"Writing ({i}/{total})…")
                    self.update_idletasks()

                # Summary footer
                duration = time.time() - start_time
                out.write(
                    f"{SEPARATOR_LINE}\n"
                    f"# SUMMARY\n"
                    f"# Files written: {files_written}/{total}\n"
                    f"# Duration: {duration:.2f} sec\n"
                    f"{SEPARATOR_LINE}\n\n"
                )
                if errors:
                    out.write("# ERRORS\n")
                    for e in errors:
                        out.write(f"# {e}\n")
                    out.write(f"{SEPARATOR_LINE}\n")

            self.status.config(text=f"Done. Wrote {files_written} file(s) to {out_path.name}")
            try:
                open_folder(str(self.output_dir))
            except Exception:
                pass
            messagebox.showinfo("Success", f"Combined TXT created:\n{out_path}")
        except Exception as e:
            traceback_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            self.status.config(text="Error during combine.")
            messagebox.showerror("Error", f"An error occurred:\n\n{e}\n\nDetails:\n{traceback_str}")
        finally:
            self.progress.config(value=0)

def main():
    app = CombineApp()
    app.mainloop()

if __name__ == "__main__":
    main()