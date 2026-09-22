"""Isolated per-attempt workspace (B7): a TemporaryDirectory holding a fresh
copy of the immutable pipeline source plus the sibling App/public layout that
`run_job.py` derives from its own file location. The repository checkout /
image copy is never mutated; the whole tree is removed in `finally`."""

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Workspace:
    tmp: tempfile.TemporaryDirectory
    root: Path
    pipeline_dir: Path
    job_dir: Path
    settings_path: Path
    status_path: Path
    video_path: Path
    data_dir: Path

    def cleanup(self) -> None:
        self.tmp.cleanup()


def build_workspace(workspace_root: str | None, pipeline_source: str, job_id: str) -> Workspace:
    tmp = tempfile.TemporaryDirectory(prefix=f"instascribe-{job_id[:8]}-", dir=workspace_root)
    root = Path(tmp.name)
    pipeline_dir = root / "modular_pipeline"
    shutil.copytree(pipeline_source, pipeline_dir)
    (root / "App" / "public" / "data").mkdir(parents=True)
    (root / "App" / "public" / "videos").mkdir(parents=True)
    job_dir = pipeline_dir / "jobs" / job_id
    job_dir.mkdir(parents=True)
    return Workspace(
        tmp=tmp,
        root=root,
        pipeline_dir=pipeline_dir,
        job_dir=job_dir,
        settings_path=job_dir / "settings.json",
        status_path=job_dir / "status.json",
        video_path=job_dir / "video.mp4",
        data_dir=root / "App" / "public" / "data" / job_id,
    )


def write_job_files(workspace: Workspace, job_id: str, stored_settings: dict) -> None:
    """Bounded settings.json (server-side job_id/video_path synthesis) and the
    seeded queued status.json — mirroring the legacy server contract."""
    settings = dict(stored_settings or {})
    settings["job_id"] = job_id
    settings["video_path"] = str(workspace.video_path)
    body = json.dumps(settings, indent=2)
    if len(body) > 64 * 1024:
        raise ValueError("settings payload exceeds the bounded size")
    workspace.settings_path.write_text(body)
    workspace.status_path.write_text(
        json.dumps(
            {
                "status": "queued",
                "progress": 0,
                "stage": "queued",
                "chunks_done": 0,
                "chunks_total": 0,
                "error": None,
            },
            indent=2,
        )
    )
