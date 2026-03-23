"""Application settings for litresearch."""

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource


class Settings(BaseSettings):
    """Environment-backed settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        toml_file="litresearch.toml",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Load settings from init, env, dotenv, TOML, then secrets."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None
    s2_api_key: str | None = None
    s2_timeout: int = 10  # seconds; SemanticScholar client timeout
    s2_requests_per_second: float = 1.0  # max S2 request rate across endpoints
    default_model: str = "openai/gpt-4o-mini"
    screening_threshold: int = 60  # 0-100; papers below this are filtered before analysis
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
