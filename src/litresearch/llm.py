"""Thin LiteLLM wrapper for the project's shared call pattern."""

from typing import Any, cast

from litellm import completion
from rich.console import Console

from litresearch.config import Settings
from litresearch.utils import retry_with_backoff

console = Console()


class LLMError(Exception):
    """Raised when an LLM request fails."""


def call_llm(
    settings: Settings,
    system_prompt: str,
    user_content: str,
    expect_json: bool = True,
) -> str:
    """Call the configured LLM and return the response content."""
    try:
        completion_kwargs = {
            "model": settings.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "timeout": settings.llm_timeout,
        }
        if expect_json:
            completion_kwargs["response_format"] = {"type": "json_object"}

        def on_retry(exc: Exception, attempt: int) -> None:
            console.print(
                f"[yellow]LLM request retry {attempt}/{settings.max_retries}:[/yellow] {exc}"
            )

        completion_with_retry = retry_with_backoff(
            max_retries=settings.max_retries,
            base_delay=settings.retry_base_delay,
            on_retry=on_retry,
        )(completion)
        response = cast(Any, completion_with_retry(**completion_kwargs))
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]LLM request failed:[/red] {exc}")
        raise LLMError(str(exc)) from exc

    content = response.choices[0].message.content
    if not isinstance(content, str):
        raise LLMError("LLM response did not contain string content")

    return content
