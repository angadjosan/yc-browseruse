"""Prompt loader: reads .md prompt files and interpolates variables."""
import os
from pathlib import Path
from typing import Any, Dict

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: Any) -> str:
    """Load a prompt from a .md file and interpolate {variables}.

    Args:
        name: Filename without extension (e.g. "risk_analysis")
        **kwargs: Variables to substitute into the prompt template

    Returns:
        The prompt string with variables substituted.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    template = path.read_text()
    if kwargs:
        template = template.format(**kwargs)
    return template
