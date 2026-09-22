"""Anthropic (Claude) providers, via the official `anthropic` SDK.

Vision sends base64 image blocks and gets structured per-scene JSON back through
a strict tool call (the model must return arguments matching the scene schema).
Text (Smart Fill) is a plain message. Set ANTHROPIC_API_KEY; install with
`pip install -r requirements-providers.txt`.

Default model is claude-opus-4-8 (override with VISION_MODEL / TEXT_MODEL /
ANTHROPIC_MODEL); claude-haiku-4-5 is a cheaper choice for the Smart Fill rewrite.
Note: Opus 4.8 rejects the `temperature` parameter, so the text provider ignores
the caller's temperature.
"""

from __future__ import annotations

from typing import Any

from .base import CaptionResult, ProviderError, TextResult


def _load():
    try:
        import anthropic
    except ImportError as exc:
        raise ProviderError(
            "Anthropic SDK not installed. Run: pip install -r requirements-providers.txt",
            retryable=False,
        ) from exc
    return anthropic


def _wrap(anthropic, exc: Exception) -> ProviderError:
    retryable = isinstance(
        exc,
        (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError),
    )
    return ProviderError(f"{type(exc).__name__}: {exc}", retryable=retryable)


class AnthropicVisionProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model

    def caption_chunk(
        self, *, developer_prompt, user_text, frames, schema, image_detail="low"
    ) -> CaptionResult:
        anthropic = _load()
        client = anthropic.Anthropic()
        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for local_idx, f in enumerate(frames):
            content.append(
                {
                    "type": "text",
                    "text": (
                        f"FRAME {local_idx}\n"
                        f"global_frame_index={f.index}\n"
                        f"timestamp={f.timestamp:.1f}s"
                    ),
                }
            )
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": f.image_b64,
                    },
                }
            )
        tool = {
            "name": schema["name"],
            "description": "Return the per-scene audio-description analysis for the given video frames.",
            "input_schema": schema["schema"],
            "strict": True,
        }
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=developer_prompt,
                messages=[{"role": "user", "content": content}],
                tools=[tool],
                tool_choice={"type": "tool", "name": schema["name"]},
            )
        except anthropic.APIError as exc:
            raise _wrap(anthropic, exc) from exc

        data = next((dict(b.input) for b in response.content if b.type == "tool_use"), None)
        if data is None:
            raise ProviderError(
                "Claude returned no tool_use block for the scene schema", retryable=True
            )
        usage = getattr(response, "usage", None)
        usage_d = None
        if usage is not None:
            usage_d = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            }
        return CaptionResult(data=data, model=self.model, usage=usage_d)


class AnthropicTextProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8") -> None:
        self.model = model

    def rewrite(self, *, system, user, temperature=0.4, max_tokens=400) -> TextResult:
        # temperature is intentionally dropped — Opus 4.8 rejects it.
        anthropic = _load()
        client = anthropic.Anthropic()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:
            raise _wrap(anthropic, exc) from exc
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        usage = getattr(response, "usage", None)
        tokens = 0
        if usage is not None:
            tokens = (getattr(usage, "input_tokens", 0) or 0) + (
                getattr(usage, "output_tokens", 0) or 0
            )
        return TextResult(text=text, model=self.model, tokens=tokens)
