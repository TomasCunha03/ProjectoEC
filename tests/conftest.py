import os
import sys
import types

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
APPS_ROOT = os.path.join(PROJECT_ROOT, "apps")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if APPS_ROOT not in sys.path:
    sys.path.insert(0, APPS_ROOT)

try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    yaml_mod = types.ModuleType("yaml")
    yaml_mod.safe_load = lambda *args, **kwargs: {}
    sys.modules["yaml"] = yaml_mod
