# src/cli/diagnose_agent_import.py
import importlib, inspect
mod = importlib.import_module("src.api.agent_reports")
print("Imported module file:", inspect.getsourcefile(mod))
print("--- First 20 lines ---")
print("\n".join(inspect.getsource(mod).splitlines()[:20]))
