import os
from pathlib import Path
from typing import Optional


def _prompts_root() -> Path:
    # backend/app/prompts
    return Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(version: str, filename: str, default: Optional[str] = None) -> str:
    """Load a prompt template from backend/app/prompts/{version}/{filename}.

    If the file does not exist, return `default` if provided, else raise FileNotFoundError.
    """
    prompts_dir = _prompts_root() / version
    path = prompts_dir / filename
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        if default is not None:
            return default
        raise
