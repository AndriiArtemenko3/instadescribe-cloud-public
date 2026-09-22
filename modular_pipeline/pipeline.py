import base64
import json
import time
from pathlib import Path
from typing import Any

from audio_whisperx_pipeline import (
    calculate_ad_gaps,
    load_audio_events,
    load_transcript,
    transcript_segment_to_dict,
)
from config import (
    CHUNK_SIZES,
    DEBUG_DIR,
    FRAMES_DIR,
    IMAGE_DETAIL,
    MEMORY_DIR,
    MODEL,
    OUTPUT_DIR,
    PROJECT_OUTPUT_DIR,
    REPORTS_DIR,
    RUNS_DIR,
    SKIP_EXISTING,
    USER_CUSTOM_PROMPT,
    VIDEO_ID,
    VIDEO_PATH,
)
from frames import FrameItem, chunk_frames, load_frames
from memory import compress_memory, load_memory, normalize_text, update_memory
from normalisation import demo_manual_override, export_app_state
from prompts import build_developer_prompt, build_user_text
from providers import Frame, ProviderError, VisionProvider, get_vision_provider
from schemas import SCENE_SCHEMA


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def safe_json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def validate_chunk_character_ids(chunk_output: dict[str, Any]) -> list[str]:
    """
    Returns IDs referenced in scenes that are not declared in memory_updates —
    neither a canonical seen_character_id nor a temp_id from new_characters.
    """
    mem_updates = chunk_output.get("memory_updates", {})
    known_ids = set(mem_updates.get("seen_character_ids", []))
    temp_ids = {
        ch.get("temp_id") for ch in mem_updates.get("new_characters", []) if ch.get("temp_id")
    }
    declared = known_ids | temp_ids

    orphaned = set()
    for scene in chunk_output.get("scenes", []):
        for cid in scene.get("character_ids", []):
            if cid not in declared:
                orphaned.add(cid)

    return sorted(orphaned)


def estimate_quality_proxy(chunk_output: dict[str, Any]) -> dict[str, Any]:
    scenes = chunk_output.get("scenes", [])
    ads = [s.get("ad", "").strip() for s in scenes]

    avg_ad_len = sum(len(a.split()) for a in ads) / len(ads) if ads else 0.0
    duplicate_ads = len(ads) - len({normalize_text(a) for a in ads if a})

    return {
        "num_scenes": len(scenes),
        "avg_ad_words": round(avg_ad_len, 2),
        "duplicate_ad_count": duplicate_ads,
    }


def analyze_chunk(
    vision: VisionProvider,
    chunk_id: int,
    chunk: list[FrameItem],
    memory: dict[str, Any],
    image_detail: str = IMAGE_DETAIL,
) -> dict[str, Any]:
    memory_context = compress_memory(memory)
    user_text = build_user_text(chunk_id, chunk, memory_context, USER_CUSTOM_PROMPT)
    frames = [
        Frame(index=frame.index, timestamp=frame.timestamp, image_b64=encode_image(frame.path))
        for frame in chunk
    ]

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]

    result = None
    for attempt in range(MAX_RETRIES):
        try:
            result = vision.caption_chunk(
                developer_prompt=build_developer_prompt(),
                user_text=user_text,
                frames=frames,
                schema=SCENE_SCHEMA,
                image_detail=image_detail,
            )
            break
        except ProviderError as e:
            if e.retryable and attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                print(
                    f"[chunk {chunk_id}] provider error ({e}), retrying in {delay}s... "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"[chunk {chunk_id}] caption call failed after {attempt + 1} attempts: {e}"
                ) from e
        except json.JSONDecodeError as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                print(
                    f"[chunk {chunk_id}] JSON parse error, retrying in {delay}s... "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"[chunk {chunk_id}] JSON parse failed after {MAX_RETRIES} attempts: {e}"
                ) from e

    if result is None:  # the loop either breaks with a result or raises
        raise RuntimeError(f"[chunk {chunk_id}] caption produced no result")

    parsed = result.data
    if result.usage is not None:
        parsed["_usage"] = {
            "input_tokens": result.usage.get("input_tokens"),
            "output_tokens": result.usage.get("output_tokens"),
            "total_tokens": result.usage.get("total_tokens"),
        }

    parsed["_meta"] = {
        "model": result.model,
        "image_detail": image_detail,
        "chunk_size": len(chunk),
    }

    return parsed


def run_for_chunk_size(
    vision: VisionProvider,
    frames: list[FrameItem],
    chunk_size: int,
) -> dict[str, Any]:
    run_dir = RUNS_DIR / f"chunk_{chunk_size}s"
    chunks_dir = run_dir / "chunks"
    memory_file = MEMORY_DIR / f"memory_chunk_{chunk_size}s.json"
    run_summary_file = REPORTS_DIR / f"summary_chunk_{chunk_size}s.json"

    chunks = chunk_frames(frames, chunk_size)
    memory = load_memory(memory_file)

    results = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    for chunk_id, chunk in enumerate(chunks):
        out_file = chunks_dir / f"chunk_{chunk_id:03d}.json"

        if SKIP_EXISTING and out_file.exists():
            chunk_output = json.loads(out_file.read_text())
        else:
            chunk_output = analyze_chunk(
                vision=vision,
                chunk_id=chunk_id,
                chunk=chunk,
                memory=memory,
            )
            safe_json_dump(out_file, chunk_output)

        orphaned = validate_chunk_character_ids(chunk_output)
        if orphaned:
            print(
                f"[chunk_size={chunk_size}] chunk={chunk_id} "
                f"WARNING: orphaned character IDs in scenes (not in memory_updates): {orphaned}"
            )

        memory = update_memory(memory, chunk_output)
        safe_json_dump(memory_file, memory)

        usage = chunk_output.get("_usage", {})
        total_input_tokens += usage.get("input_tokens") or 0
        total_output_tokens += usage.get("output_tokens") or 0
        total_tokens += usage.get("total_tokens") or 0

        quality_proxy = estimate_quality_proxy(chunk_output)

        results.append(
            {
                "chunk_id": chunk_id,
                "chunk_start": chunk_output.get("chunk_start"),
                "chunk_end": chunk_output.get("chunk_end"),
                "usage": usage,
                "quality_proxy": quality_proxy,
                "num_scenes": len(chunk_output.get("scenes", [])),
                "global_summary": chunk_output.get("global_summary", ""),
            }
        )

        print(
            f"[chunk_size={chunk_size}] chunk={chunk_id}/{len(chunks) - 1} "
            f"scenes={len(chunk_output.get('scenes', []))} "
            f"tokens={usage.get('total_tokens')}"
        )

    summary = {
        "video_id": VIDEO_ID,
        "chunk_size": chunk_size,
        "num_chunks": len(chunks),
        "total_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
        },
        "chunks": results,
        "final_memory_file": str(memory_file),
        "chunks_dir": str(chunks_dir),
    }

    safe_json_dump(run_summary_file, summary)
    return summary


def build_comparison_report(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(values: list[float]) -> float | None:
        if not values:
            return None
        return sum(values) / len(values)

    comparison = {"video_id": VIDEO_ID, "runs": []}

    for s in summaries:
        chunk_stats = s["chunks"]

        avg_num_scenes = mean([c["num_scenes"] for c in chunk_stats]) or 0.0
        avg_ad_words = mean([c["quality_proxy"]["avg_ad_words"] for c in chunk_stats]) or 0.0
        avg_dup_ads = mean([c["quality_proxy"]["duplicate_ad_count"] for c in chunk_stats]) or 0.0

        comparison["runs"].append(
            {
                "chunk_size": s["chunk_size"],
                "num_chunks": s["num_chunks"],
                "total_tokens": s["total_usage"]["total_tokens"],
                "avg_scenes_per_chunk": round(avg_num_scenes, 2),
                "avg_ad_words": round(avg_ad_words, 2),
                "avg_duplicate_ads": round(avg_dup_ads, 2),
                "summary_file": str(REPORTS_DIR / f"summary_chunk_{s['chunk_size']}s.json"),
            }
        )

    return comparison


def main() -> None:
    vision = get_vision_provider()

    PROJECT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    frames = load_frames(FRAMES_DIR)
    print(f"Loaded {len(frames)} frames from {FRAMES_DIR.resolve()}")

    audio_events = load_audio_events(VIDEO_PATH, frames)
    print(f"Loaded {len(audio_events)} audio events from {VIDEO_PATH.name}")

    audio_events_payload = [
        {
            "start": e.start,
            "end": e.end,
            "event_type": e.event_type,
            "confidence": e.confidence,
            "transcript": e.transcript,
        }
        for e in audio_events
    ]
    safe_json_dump(OUTPUT_DIR / "audio_events.json", audio_events_payload)
    print(f"Saved {len(audio_events)} audio events → output/audio_events.json")

    gaps = calculate_ad_gaps(audio_events)
    safe_json_dump(OUTPUT_DIR / "ad_placement_gaps.json", gaps)
    print(f"Saved {len(gaps)} AD placement gaps → output/ad_placement_gaps.json")
    transcript = load_transcript(VIDEO_PATH, frames)
    transcript_payload = [transcript_segment_to_dict(s) for s in transcript]
    safe_json_dump(OUTPUT_DIR / "transcript.json", transcript_payload)
    print(f"Saved {len(transcript)} transcript segments → output/transcript.json")

    summaries = []
    for chunk_size in CHUNK_SIZES:
        print(f"\n=== Running chunk size: {chunk_size} ===")
        summary = run_for_chunk_size(vision, frames, chunk_size)
        summaries.append(summary)

    comparison = build_comparison_report(summaries)
    comparison_path = REPORTS_DIR / "comparison_report.json"
    safe_json_dump(comparison_path, comparison)

    print("\nDone.")
    print(f"Comparison report saved to: {comparison_path.resolve()}")

    final_memory_file = MEMORY_DIR / f"memory_chunk_{CHUNK_SIZES[-1]}s.json"
    if not final_memory_file.exists():
        raise FileNotFoundError(
            f"Expected final memory file not found: {final_memory_file}. "
            "Check that at least one chunk size ran successfully."
        )
    try:
        final_memory = json.loads(final_memory_file.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupt final memory file {final_memory_file}: {e}") from e

    export_app_state(
        memory=final_memory,
        summaries=summaries,
        out_dir=OUTPUT_DIR,
        video_id=VIDEO_ID,
        model=MODEL,
        image_detail=IMAGE_DETAIL,
        chunk_sizes=CHUNK_SIZES,
        num_frames=len(frames),
    )

    demo_manual_override(memory=final_memory, out_dir=OUTPUT_DIR)


if __name__ == "__main__":
    main()
