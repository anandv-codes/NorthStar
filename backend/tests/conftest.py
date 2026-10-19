"""Shared pytest setup.

Ensures the repository root is importable so tests can use
``backend.app.*`` regardless of the directory pytest is invoked from.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
