"""OpenAI-backed providers — the default backend.

These also work against any OpenAI-compatible server by setting OPENAI_BASE_URL
(Ollama, vLLM, LM Studio, OpenRouter), which covers vision and text. Hosted TTS
has no drop-in local-compatible endpoint, so for a fully keyless setup use the
`local` (Kokoro) TTS provider.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import openai
from api_settings import get_client, safe_create_response

from .base import CaptionResult, ProviderError, TextResult

_RETRYABLE = (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError)


def _wrap(exc: Exception) -> ProviderError:
    return ProviderError(f"{type(exc).__name__}: {exc}", retryable=isinstance(exc, _RETRYABLE))


class OpenAIVisionProvider:
    name = "openai"

    def __init__(self, model: str = "gpt-4.1") -> None:
        self.model = model

    def caption_chunk(
        self, *, developer_prompt, user_text, frames, schema, image_detail="low"
    ) -> CaptionResult:
        client = get_client()
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user_text}]
        for local_idx, f in enumerate(frames):
            content.append(
                {
                    "type": "input_text",
                    "text": (
                        f"FRAME {local_idx}\n"
                        f"global_frame_index={f.index}\n"
                        f"timestamp={f.timestamp:.1f}s"
                    ),
                }
            )
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{f.image_b64}",
                    "detail": image_detail,
                }
            )
        try:
            response = safe_create_response(
                client,
                model=self.model,
                input=[
                    {
                        "role": "developer",
                        "content": [{"type": "input_text", "text": developer_prompt}],
                    },
                    {"role": "user", "content": content},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema["name"],
                        "schema": schema["schema"],
                        "strict": schema["strict"],
                    }
                },
            )
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc

        data = json.loads(response.output_text)  # JSONDecodeError -> caller retries
        usage = getattr(response, "usage", None)
        usage_d = None
        if usage is not None:
            usage_d = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
        return CaptionResult(data=data, model=self.model, usage=usage_d)


class OpenAITextProvider:
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model

    def rewrite(self, *, system, user, temperature=0.4, max_tokens=400) -> TextResult:
        client = get_client()
        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc
        text = (completion.choices[0].message.content or "").strip()
        tokens = completion.usage.total_tokens if completion.usage else 0
        return TextResult(text=text, model=self.model, tokens=tokens)


class OpenAITTSProvider:
    name = "openai"
    voices = ("onyx", "nova", "alloy", "shimmer", "echo", "fable")

    def __init__(self, model: str = "tts-1-hd") -> None:
        self.model = model

    def _voice(self, voice: str | None) -> str:
        v = (voice or "onyx").strip().lower()
        return v if v in self.voices else "onyx"

    def synthesize(self, *, text, voice, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        client = get_client()
        try:
            response = client.audio.speech.create(
                model=self.model, voice=self._voice(voice), input=text
            )
            response.stream_to_file(out_path)
        except openai.OpenAIError as exc:
            raise _wrap(exc) from exc
        return out_path
