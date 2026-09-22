"""Provider-neutral interfaces for the three model-backed stages of the pipeline.

The pipeline needs exactly three model capabilities:

  * vision  — caption a chunk of video frames as structured JSON (per-scene AD).
  * text    — rewrite one AD line to fit a time budget (Smart Fill).
  * tts      — speak one AD line to an audio file.

Each capability is a small `Protocol`. Concrete backends live alongside this
file (`openai_provider`, `local_provider`, `fake_provider`) and are selected at
runtime by `factory.py` from environment variables, so no call site imports a
vendor SDK directly. Speech detection and transcription stay local (they never
called a hosted API) and are out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class ProviderError(Exception):
    """A model call failed. `retryable` marks transient faults (rate limit,
    timeout, connection) so the caller can back off and retry; permanent faults
    (bad request, auth, unreachable local server) set it False and fail fast."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Frame:
    """One sampled video frame handed to a vision provider."""

    index: int  # global frame index in the source video
    timestamp: float  # seconds from the start of the clip
    image_b64: str  # base64-encoded JPEG bytes, no `data:` prefix


@dataclass
class CaptionResult:
    data: dict[str, Any]  # parsed JSON, conforming to the caller's schema
    model: str
    usage: dict[str, Any] | None = None  # token counts when the backend reports them


@dataclass
class TextResult:
    text: str
    model: str
    tokens: int = 0


@runtime_checkable
class VisionProvider(Protocol):
    name: str

    def caption_chunk(
        self,
        *,
        developer_prompt: str,
        user_text: str,
        frames: list[Frame],
        schema: dict[str, Any],
        image_detail: str = "low",
    ) -> CaptionResult:
        """Describe the frames as JSON matching `schema` (an OpenAI-style
        `{name, schema, strict}` json_schema descriptor). Raise `ProviderError`
        on failure."""
        ...


@runtime_checkable
class TextProvider(Protocol):
    name: str

    def rewrite(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.4,
        max_tokens: int = 400,
    ) -> TextResult:
        """Return the rewritten text. Raise `ProviderError` on failure."""
        ...


@runtime_checkable
class TTSProvider(Protocol):
    name: str
    voices: tuple[str, ...]

    def synthesize(self, *, text: str, voice: str, out_path: Path) -> Path:
        """Write spoken `text` to `out_path` (mp3) and return it. `voice` is a
        provider-neutral name; each backend maps it to its own voice set and
        falls back to a sensible default for unknown names."""
        ...
