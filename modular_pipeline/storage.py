"""Filesystem layout and per-job persistence.

All on-disk paths and the read/modify/write of a job's status, meta, and scene
overrides live here, so the route handlers stay thin. Tests redirect storage by
monkeypatching the module-level directory constants.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent  # modular_pipeline/
APP_DIR = SERVER_DIR.parent / "App"
VIDEOS_DIR = APP_DIR / "public" / "videos"
DATA_DIR = APP_DIR / "public" / "data"
DIST_DIR = APP_DIR / "dist"
JOBS_DIR = SERVER_DIR / "jobs"
PYTHON = sys.executable  # same venv python, used to launch run_job.py


# ─── Path builders ──────────────────────────────────────────────────────────


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def status_file(job_id: str) -> Path:
    return job_dir(job_id) / "status.json"


def meta_path(job_id: str) -> Path:
    return job_dir(job_id) / "meta.json"


def overrides_path(job_id: str) -> Path:
    return job_dir(job_id) / "scene_overrides.json"


def tts_cache_dir(job_id: str) -> Path:
    return job_dir(job_id) / "tts_cache"


def exports_root(job_id: str) -> Path:
    return job_dir(job_id) / "exports"


def export_dir(job_id: str, export_id: str) -> Path:
    return exports_root(job_id) / export_id


# ─── Status / meta ──────────────────────────────────────────────────────────


def read_status(job_id: str) -> dict:
    sf = status_file(job_id)
    if not sf.exists():
        return {"status": "not_found", "progress": 0, "stage": "unknown", "error": None}
    try:
        return json.loads(sf.read_text())
    except Exception:
        return {
            "status": "error",
            "progress": 0,
            "stage": "unknown",
            "error": "Corrupt status file",
        }


def read_meta(job_id: str) -> dict:
    p = meta_path(job_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def write_meta(job_id: str, meta: dict) -> None:
    meta_path(job_id).write_text(json.dumps(meta, indent=2))


# ─── Scene overrides (lock-protected read-modify-write) ─────────────────────
#
# The editor flushes every scene's state in parallel before a preview/export
# (one PATCH per scene). Without a per-job lock those concurrent
# read-whole-file → change-one → write-whole-file cycles drop each other's
# updates, and a dropped scene falls back to active=True in the merge — so a
# deactivated scene would wrongly get narrated.

_overrides_locks: dict[str, threading.Lock] = {}
_overrides_locks_guard = threading.Lock()


def overrides_lock(job_id: str) -> threading.Lock:
    with _overrides_locks_guard:
        lock = _overrides_locks.get(job_id)
        if lock is None:
            lock = threading.Lock()
            _overrides_locks[job_id] = lock
        return lock


def read_overrides(job_id: str) -> dict:
    p = overrides_path(job_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def write_overrides(job_id: str, overrides: dict) -> None:
    # Write atomically (temp file + rename) so a concurrent reader — e.g. an export
    # building its merged scene list — never sees a half-written, unparseable file.
    path = overrides_path(job_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(overrides, indent=2))
    os.replace(tmp, path)


def video_url_for(job_id: str) -> str | None:
    """Resolve a job's playable video URL. Prefer result.json, fall back to disk."""
    rp = job_dir(job_id) / "result.json"
    if rp.exists():
        try:
            recorded = json.loads(rp.read_text()).get("video_file")
            if recorded:
                return recorded
        except Exception:
            pass
    public = VIDEOS_DIR / f"{job_id}.mp4"
    if public.exists():
        return f"/videos/{job_id}.mp4"
    source = job_dir(job_id) / "video.mp4"
    if source.exists():
        try:
            VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(public))
            return f"/videos/{job_id}.mp4"
        except Exception:
            return None
    return None
