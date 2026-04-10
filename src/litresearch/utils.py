"""Utility functions for litresearch."""

import functools
import hashlib
import json
import re
import time
import uuid
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError
from rich.console import Console


class LLMJSONError(Exception):
    """Raised when LLM response cannot be parsed or validated."""


def parse_llm_json(
    response: str,
    model_class: type[BaseModel] | None = None,
    console: Console | None = None,
) -> dict[str, Any] | None:
    """Parse LLM JSON response with comprehensive error handling.

    Returns None when decoding or validation fails.
    """
    try:
        data = json.loads(response)
    except json.JSONDecodeError as exc:
        if console:
            console.print(f"[yellow]JSON decode failed:[/yellow] {exc}")
        return None

    if not isinstance(data, dict):
        if console:
            console.print("[yellow]JSON parse failed:[/yellow] response must be an object")
        return None

    if model_class is not None:
        try:
            validated = model_class.model_validate(data)
            return validated.model_dump()
        except ValidationError as exc:
            if console:
                console.print(f"[yellow]Validation failed:[/yellow] {exc}")
            return None

    return data


T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry decorator with exponential backoff and jitter."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_retries:
                        raise

                    delay = min(base_delay * (2**attempt), max_delay)
                    delay *= 0.5 + ((uuid.uuid4().int % 500) / 1000)

                    if on_retry:
                        on_retry(exc, attempt + 1)

                    time.sleep(delay)

            if last_exception is None:
                raise RuntimeError("retry_with_backoff exhausted without exception")
            raise last_exception

        return wrapper

    return decorator


def safe_filename(paper_id: str) -> str:
    """Sanitize paper_id for safe use in filenames.

    Replaces characters that are illegal in filenames with underscores.
    Falls back to hash if the result would be empty.
    """
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", paper_id)

    if len(sanitized) > 200:
        sanitized = sanitized[:200]

    if not sanitized or sanitized.startswith(".") or sanitized in {".", ".."}:
        sanitized = hashlib.md5(paper_id.encode()).hexdigest()[:16]

    return sanitized
