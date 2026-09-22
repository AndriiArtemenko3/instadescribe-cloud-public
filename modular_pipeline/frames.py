import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FrameItem:
    index: int
    timestamp: float
    path: Path


def parse_timestamp_from_filename(path: Path, fallback_index: int) -> float:
    stem = path.stem
    # Primary format written by frame_extraction.py: frame_XXXX
    # where XXXX = int(round(timestamp_seconds * 10))
    # Dividing by 10 recovers the actual timestamp regardless of FPS.
    # e.g. frame_0020.jpg → 20/10 = 2.0s, frame_0620.jpg → 62.0s
    m = re.match(r"^frame_(\d+)$", stem)
    if m:
        return int(m.group(1)) / 10.0

    # Fallback for other naming conventions: take the last number in the stem
    matches = re.findall(r"(\d+(?:\.\d+)?)", stem)
    if len(matches) >= 2:
        try:
            return float(matches[-1])
        except ValueError:
            pass

    return float(fallback_index)


def load_frames(frames_dir: Path) -> list[FrameItem]:
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp")
    files = []
    for ext in exts:
        files.extend(sorted(frames_dir.glob(ext)))

    if not files:
        raise FileNotFoundError(f"No frames found in {frames_dir.resolve()}")

    frame_items = []
    for idx, path in enumerate(sorted(files)):
        timestamp = parse_timestamp_from_filename(path, idx)
        frame_items.append(FrameItem(index=idx, timestamp=timestamp, path=path))

    return frame_items


def chunk_frames(frames: list[FrameItem], chunk_size: int) -> list[list[FrameItem]]:
    return [frames[i : i + chunk_size] for i in range(0, len(frames), chunk_size)]


def estimate_chunk_coverage(chunk: list[FrameItem]) -> tuple[float, float]:
    if not chunk:
        return 0.0, 0.0
    return chunk[0].timestamp, chunk[-1].timestamp
