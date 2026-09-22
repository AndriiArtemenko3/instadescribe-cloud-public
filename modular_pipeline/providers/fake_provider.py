"""Deterministic, dependency-free providers.

They make no network call and need no key, model, or GPU, so they power the test
suite and a keyless server smoke run (INSTASCRIBE_BACKEND=fake). The frontend
demo build has its own equivalent in App/src/lib/demoApi.ts; this is the backend
mirror of that idea. Output is placeholder text, not a real description.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import CaptionResult, TextResult

_WPS = 2.3  # AD delivered at ~2.3 words/sec, matching the server + demo constants


class FakeVisionProvider:
    name = "fake"

    def caption_chunk(
        self, *, developer_prompt, user_text, frames, schema, image_detail="low"
    ) -> CaptionResult:
        start = frames[0].timestamp if frames else 0.0
        end = frames[-1].timestamp if frames else 0.0
        # The last synthetic scene spans one sampling interval past its frame:
        # real providers never emit zero-length scenes (see the committed demo
        # fixture), and the G5.1 artifact contract enforces end > start, so
        # the placeholder geometry must respect the same schema.
        if len(frames) > 1:
            interval = max(frames[-1].timestamp - frames[-2].timestamp, 0.1)
        else:
            interval = 1.0
        last_end = (frames[-1].timestamp + interval) if frames else 0.0
        scenes = [
            {
                "scene_id": i,
                "start": f.timestamp,
                "end": (frames[i + 1].timestamp if i + 1 < len(frames) else last_end),
                "frame_indices": [f.index],
                "character_ids": [],
                "ad": f"Placeholder description at {f.timestamp:.1f} seconds (no model call).",
                "ad_template": "Placeholder description (no model call).",
                "reason_for_split": "fake provider: one scene per frame",
            }
            for i, f in enumerate(frames)
        ]
        data = {
            "chunk_id": 0,
            "chunk_start": start,
            "chunk_end": end,
            "global_summary": "Placeholder summary produced by the fake provider.",
            "scenes": scenes,
            "memory_updates": {"seen_character_ids": [], "new_characters": []},
        }
        return CaptionResult(data=data, model="fake", usage={"total_tokens": 0})


class FakeTextProvider:
    name = "fake"

    def rewrite(self, *, system, user, temperature=0.4, max_tokens=400) -> TextResult:
        # Pull the description and word budget out of the smart-fill prompt, then
        # trim deterministically — keep the leading clause, drop the tail.
        text = user
        if "Current description:" in user:
            text = user.split("Current description:", 1)[1].strip().split("\n\n", 1)[0].strip()
        words = [w for w in text.split() if w]
        m = re.search(r"~(\d+)\s+words", user)
        budget = int(m.group(1)) if m else max(3, len(words) // 2)
        kept = words[: max(3, budget)]
        ad = " ".join(kept)
        if kept and len(kept) < len(words):
            ad = ad.rstrip(",;:") + "."
        return TextResult(text=ad or text, model="fake", tokens=0)


class FakeTTSProvider:
    name = "fake"
    voices = ("onyx",)

    def synthesize(self, *, text, voice, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Serve the committed silence fixture when available; else an empty file.
        silence = Path(__file__).resolve().parents[2] / "App" / "public" / "demo" / "silence.mp3"
        out_path.write_bytes(silence.read_bytes() if silence.exists() else b"")
        return out_path
