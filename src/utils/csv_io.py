
# src/utils/csv_io.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence
from fastapi.responses import StreamingResponse
import csv
import io


def dicts_to_csv_stream(
    rows: Iterable[Dict[str, Any]],
    field_order: Optional[Sequence[str]] = None,
    filename: Optional[str] = None,
) -> StreamingResponse:
    """
    Stream a CSV built from a list/iterable of dict rows.
    - If field_order is None, infer headers from the first row's keys.
    - Silently ignores extra keys present in rows but not in field_order.
    """
    buf = io.StringIO()
    rows_list = list(rows)
    if rows_list:
        headers = list(field_order) if field_order else list(rows_list[0].keys())
        writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows_list:
            writer.writerow(r)
    buf.seek(0)
    headers = {"Content-Type": "text/csv; charset=utf-8"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return StreamingResponse(buf, headers=headers)


def rows_to_csv_stream(
    rows: Iterable[Iterable[Any]],
    filename: Optional[str] = None,
) -> StreamingResponse:
    """
    Stream a CSV built from a list/iterable of row sequences (no headers).
    Useful for template-style exports (e.g., Book1.csv clones).
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(list(r))
    buf.seek(0)
    headers = {"Content-Type": "text/csv; charset=utf-8"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return StreamingResponse(buf, headers=headers)
