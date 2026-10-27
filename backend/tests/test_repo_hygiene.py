"""Guards for dead weight that was deleted deliberately.

Each path below was unreferenced code or tooling debris. Re-adding one is
almost certainly an accident, so this fails loudly instead of letting the
"what is this directory?" question drift back into the repo.

Note: these paths are also in ``.gitignore``, so the check is on the working
tree rather than on git.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DEAD_PATHS = [
    "backend/app/handlers",
    "backend/package.json",
    "backend/package-lock.json",
    "backend/chroma_data",
    "chroma_data",
    "backend/node_modules",
]


@pytest.mark.parametrize("relative_path", DEAD_PATHS)
def test_dead_weight_paths_stay_deleted(relative_path: str):
    path = REPO_ROOT / relative_path
    assert not path.exists(), (
        f"{relative_path} was deleted as unreferenced dead weight; "
        "if it is needed again, update this test and explain why in the commit."
    )
