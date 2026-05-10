"""Application settings for litresearch."""

from typing import Literal

from pydantic import computed_field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


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
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
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
    max_retries: int = 3
    retry_base_delay: float = 1.0
    llm_timeout: int = 120
    default_model: str = "openai/gpt-4o-mini"
    screening_selection_mode: Literal["top_percent", "threshold", "top_k"] = "top_percent"
    screening_top_percent: float = 0.3  # 0-1; used when screening_selection_mode=top_percent
    screening_top_k: int | None = None  # used when screening_selection_mode=top_k
    screening_threshold: int = 60  # 0-100; used when screening_selection_mode=threshold
    top_n: int = 20
    max_results_per_query: int = 20

    # Discovery sources
    discovery_sources: list[str] = ["s2"]
    openalex_email: str | None = None

    # Citation expansion
    expand_citations: bool = False
    min_cross_refs: int = 3

    # Zotero export
    zotero_library_id: str | None = None
    zotero_api_key: str | None = None
    zotero_library_type: Literal["user", "group"] = "user"
    zotero_collection_key: str | None = None
    zotero_tag: str | None = None
    zotero_export: bool = False

    pdf_first_pages: int = 4
    pdf_last_pages: int = 2
    pdf_extraction_mode: Literal["budget", "pages"] = "budget"
    pdf_token_budget: int = 4000
    abstract_fallback: bool = True
    inject_pdf_dir: str | None = None
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
