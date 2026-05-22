import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
APPS_ROOT = os.path.join(PROJECT_ROOT, "apps")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if APPS_ROOT not in sys.path:
    sys.path.insert(0, APPS_ROOT)
