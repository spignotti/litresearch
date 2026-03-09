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
    default_model: str = "openai/gpt-4o-mini"
    screening_threshold: int = 40
    top_n: int = 20
    max_results_per_query: int = 20
    pdf_first_pages: int = 4
    pdf_last_pages: int = 2
    output_dir: str = "output"

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
