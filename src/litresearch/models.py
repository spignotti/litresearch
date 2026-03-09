"""Shared data models for the litresearch scaffold."""

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Minimal input model for future pipeline work."""

    questions: list[str] = Field(default_factory=list)
