"""
Shared LLM utility functions for agent modules.

Consolidates duplicated helpers that were previously defined in both
planning.py and conclusion.py.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI


def create_structured_completion(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    max_tokens: int,
    temperature: float,
):
    """Call an OpenAI-compatible structured outputs endpoint."""
    return client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": schema,
        },
    )
