"""Prompt template loading helpers."""

from importlib import resources


def load_prompt(name: str) -> str:
    """Load a markdown prompt template from the prompts package."""
    resource = resources.files(__package__).joinpath(f"{name}.md")
    return resource.read_text(encoding="utf-8")
