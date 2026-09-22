import subprocess
from pathlib import Path


def get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def extract_frame_at(t: float, video_path: Path, out_dir: Path) -> Path:
    t10 = int(round(t * 10))
    out_path = out_dir / f"frame_{t10:04d}.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(t),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path


def extract_frames(video_path: Path, out_dir: Path, step: float = 1.0) -> int:
    """Extract frames from video_path into out_dir at the given step interval.

    Returns the number of frames written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = get_video_duration(video_path)
    count = 0
    t = 0.0
    while t < duration:
        p = extract_frame_at(t, video_path, out_dir)
        if p.exists():
            count += 1
        t = round(t + step, 6)
    return count


# ─── CLI (backward-compatible) ────────────────────────────────────────────────

if __name__ == "__main__":
    VIDEO = Path("../clips/vibe.mp4")
    OUT_DIR = Path("out_6/frames_vibe/")
    STEP = 1.0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = extract_frames(VIDEO, OUT_DIR, STEP)
    print(f"\nExtracted {count} frames to {OUT_DIR}")
