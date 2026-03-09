"""Application settings for litresearch."""

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None
    s2_api_key: str | None = None
    default_model: str = "gpt-4o-mini"

    @computed_field
    @property
    def has_llm_api_key(self) -> bool:
        """Return whether any supported LLM provider key is configured."""
        return any(
            [
                self.openai_api_key,
                self.anthropic_api_key,
                self.openrouter_api_key,
            ]
        )
