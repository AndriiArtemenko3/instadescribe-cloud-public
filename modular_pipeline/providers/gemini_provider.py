"""Google Gemini providers, via Gemini's OpenAI-compatibility endpoint.

Reuses the `openai` client already in requirements.txt (no extra package) pointed
at Gemini's OpenAI-compatible base URL. Vision + structured output go through the
shared `_compat` helper. Set GEMINI_API_KEY (or GOOGLE_API_KEY).

Default model is gemini-2.5-flash (override with VISION_MODEL / TEXT_MODEL /
GEMINI_MODEL; newer ids like gemini-3.5-flash work too).
"""

from __future__ import annotations

import os

import openai

from . import _compat
from .base import CaptionResult, ProviderError, TextResult

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_HINT = "Set GEMINI_API_KEY (or GOOGLE_API_KEY)."


def _client() -> openai.OpenAI:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ProviderError(
            "Missing GEMINI_API_KEY (or GOOGLE_API_KEY) for the Gemini backend", retryable=False
        )
    return openai.OpenAI(base_url=os.getenv("GEMINI_BASE_URL", _BASE_URL), api_key=key)


class GeminiVisionProvider:
    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        self.model = model

    def caption_chunk(
        self, *, developer_prompt, user_text, frames, schema, image_detail="low"
    ) -> CaptionResult:
        return _compat.caption_chunk(
            _client(),
            self.model,
            developer_prompt=developer_prompt,
            user_text=user_text,
            frames=frames,
            schema=schema,
            service="Gemini",
            hint=_HINT,
        )


class GeminiTextProvider:
    name = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        self.model = model

    def rewrite(self, *, system, user, temperature=0.4, max_tokens=400) -> TextResult:
        return _compat.rewrite(
            _client(),
            self.model,
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
            service="Gemini",
            hint=_HINT,
        )
