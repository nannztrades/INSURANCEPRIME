from __future__ import annotations
import argparse
from importlib import import_module
from fastapi.routing import APIRoute
from typing import List


def load_app():
    # Use your dynamic router registration main
    mod = import_module("src.main")
    return getattr(mod, "app")


def list_routes(fmt: str = "table"):
    app = load_app()
    rows: List[dict] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            # Coerce to str first so type-checkers see Iterable[str]
            methods_list: List[str] = [str(m) for m in route.methods]
            methods = ",".join(sorted(methods_list))

            tags_list: List[str] = [str(t) for t in (route.tags or [])]
            tags = ",".join(tags_list)

            path = route.path
            name = route.name
            rows.append({"methods": methods, "path": path, "name": name, "tags": tags})
    if fmt == "csv":
        print("methods,path,name,tags")
        for r in rows:
            print(f"{r['methods']},{r['path']},{r['name']},{r['tags']}")
    else:
        # pretty table
        if not rows:
            print("No routes found.")
            return
        w_m = max(6, *(len(r["methods"]) for r in rows))
        w_p = max(6, *(len(r["path"]) for r in rows))
        w_n = max(6, *(len(r["name"]) for r in rows))
        w_t = max(6, *(len(r["tags"]) for r in rows))
        print(f"{'METHODS'.ljust(w_m)}  {'PATH'.ljust(w_p)}  {'NAME'.ljust(w_n)}  {'TAGS'.ljust(w_t)}")
        print("-" * (w_m + w_p + w_n + w_t + 6))
        for r in rows:
            print(f"{r['methods'].ljust(w_m)}  {r['path'].ljust(w_p)}  {r['name'].ljust(w_n)}  {r['tags'].ljust(w_t)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="List all FastAPI routes")
    ap.add_argument("--format", choices=["table", "csv"], default="table")
    args = ap.parse_args()
    list_routes(fmt=args.format)