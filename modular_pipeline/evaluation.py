"""AD-quality evaluation harness.

Scores a set of audio-description scenes against five rubric dimensions and flags
the specific scenes that need attention. Pure and dependency-free, so the same
scoring runs in the API, in tests, and — mirrored in App/src/lib/evaluation.ts —
live in the editor with no model call.

Dimensions (each 0..1, over active non-empty scenes):
  timing                 — narration fits inside the scene's time window
  dialogue_safety        — narration does not talk over dialogue
  coverage               — share of the video that carries an active description
  character_consistency  — every referenced character id resolves to an entity
  grounding              — proxy: penalises duplicated descriptions
"""

from __future__ import annotations

import re

SECS_PER_WORD = 0.4  # ~150 wpm narration; mirrors collisions.ts
AD_START_OFFSET = 0.25  # AD voiced just after the scene begins; mirrors the export mux
COLLISION_TOLERANCE = 0.5  # ignore sub-half-second overlaps as rounding

WEIGHTS = {
    "timing": 0.25,
    "dialogue_safety": 0.30,
    "coverage": 0.15,
    "character_consistency": 0.15,
    "grounding": 0.15,
}


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def estimate_speech_secs(text: str | None, speed: float = 1.0) -> float:
    words = [w for w in _norm(text).split(" ") if w]
    if not words:
        return 0.0
    safe_speed = speed if speed and speed > 0 else 1.0
    return len(words) * SECS_PER_WORD / safe_speed


def _dialogue_overlap(ad_start: float, ad_end: float, audio_events: list[dict]) -> float:
    total = 0.0
    for ev in audio_events:
        if (ev.get("event_type") or ev.get("type")) != "dialogue":
            continue
        start = max(ad_start, float(ev.get("start", 0.0)))
        end = min(ad_end, float(ev.get("end", 0.0)))
        if end > start:
            total += end - start
    return total


def evaluate_ad(
    scenes: list[dict],
    audio_events: list[dict],
    entities: list[dict],
    duration_secs: float,
) -> dict:
    """Score the active descriptions. `scenes` are merged-scene dicts
    (start/end/text/active/speed/character_ids)."""
    entity_ids = {e.get("id") for e in entities}
    active = [s for s in scenes if s.get("active", True) and _norm(s.get("text", ""))]
    n = len(active)

    if n == 0:
        return {
            "overall": 0.0,
            "dimensions": {k: 0.0 for k in WEIGHTS},
            "flags": [],
            "active_count": 0,
        }

    text_counts: dict[str, int] = {}
    for s in active:
        key = _norm(s.get("text", ""))
        text_counts[key] = text_counts.get(key, 0) + 1

    timing_ok = safe = consistent = duplicates = 0
    covered = 0.0
    dur = duration_secs if duration_secs and duration_secs > 0 else None
    flags: list[dict] = []

    for s in active:
        issues: list[str] = []
        start = float(s.get("start", 0.0))
        end = float(s.get("end", start))
        speed = float(s.get("speed", 1.0) or 1.0)
        est = estimate_speech_secs(s.get("text", ""), speed)

        if est <= max(0.0, end - start):
            timing_ok += 1
        else:
            issues.append("narration_too_long")

        ad_start = start + AD_START_OFFSET
        if _dialogue_overlap(ad_start, ad_start + est, audio_events) > COLLISION_TOLERANCE:
            issues.append("dialogue_collision")
        else:
            safe += 1

        char_ids = s.get("character_ids") or []
        if all(cid in entity_ids for cid in char_ids):
            consistent += 1
        else:
            issues.append("orphan_character")

        if text_counts[_norm(s.get("text", ""))] > 1:
            duplicates += 1
            issues.append("duplicate_text")

        if dur:
            covered += max(0.0, min(end, dur) - start)

        if issues:
            flags.append({"scene_id": s.get("scene_id", ""), "issues": issues})

    dims = {
        "timing": timing_ok / n,
        "dialogue_safety": safe / n,
        "coverage": min(1.0, covered / dur) if dur else 0.0,
        "character_consistency": consistent / n,
        "grounding": 1.0 - duplicates / n,
    }
    overall = sum(dims[k] * w for k, w in WEIGHTS.items())
    return {
        "overall": round(overall, 4),
        "dimensions": {k: round(v, 4) for k, v in dims.items()},
        "flags": flags,
        "active_count": n,
    }
