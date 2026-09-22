"""Shared call logic for OpenAI-compatible chat endpoints.

Ollama, Gemini (via its OpenAI-compatibility layer), vLLM, LM Studio, and
OpenRouter all speak the same `chat.completions` wire format: vision goes through
`image_url` content blocks and structured output through `response_format`
json_schema. Each provider builds an `openai.OpenAI` client (its own base_url +
key) and calls these helpers, so the request shape lives in one place.
"""

from __future__ import annotations

import json
from typing import Any

import openai

from .base import CaptionResult, ProviderError, TextResult

_RETRYABLE = (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError)


def wrap_error(exc: Exception, *, service: str, hint: str = "") -> ProviderError:
    if isinstance(exc, openai.APIConnectionError):
        return ProviderError(f"Cannot reach {service}. {hint} ({exc})".strip(), retryable=True)
    return ProviderError(f"{type(exc).__name__}: {exc}", retryable=isinstance(exc, _RETRYABLE))


def caption_chunk(
    client: openai.OpenAI,
    model: str,
    *,
    developer_prompt: str,
    user_text: str,
    frames,
    schema: dict[str, Any],
    service: str,
    hint: str = "",
) -> CaptionResult:
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for local_idx, f in enumerate(frames):
        content.append(
            {
                "type": "text",
                "text": (
                    f"FRAME {local_idx}\nglobal_frame_index={f.index}\ntimestamp={f.timestamp:.1f}s"
                ),
            }
        )
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{f.image_b64}"}}
        )
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": developer_prompt},
                {"role": "user", "content": content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema["name"],
                    "schema": schema["schema"],
                    "strict": schema.get("strict", True),
                },
            },
            temperature=0,
        )
    except openai.OpenAIError as exc:
        raise wrap_error(exc, service=service, hint=hint) from exc

    raw = completion.choices[0].message.content or "{}"
    data = json.loads(raw)  # JSONDecodeError -> caller retries
    usage = getattr(completion, "usage", None)
    usage_d = {"total_tokens": getattr(usage, "total_tokens", None)} if usage else None
    return CaptionResult(data=data, model=model, usage=usage_d)


def rewrite(
    client: openai.OpenAI,
    model: str,
    *,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    service: str,
    hint: str = "",
) -> TextResult:
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except openai.OpenAIError as exc:
        raise wrap_error(exc, service=service, hint=hint) from exc
    text = (completion.choices[0].message.content or "").strip()
    usage = getattr(completion, "usage", None)
    tokens = (getattr(usage, "total_tokens", 0) or 0) if usage else 0
    return TextResult(text=text, model=model, tokens=tokens)
