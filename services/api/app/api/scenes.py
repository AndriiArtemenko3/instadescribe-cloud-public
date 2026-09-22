"""Scene-override routes (G6 Gate 3).

PATCH /jobs/{job_id}/scenes/{scene_id}  — strict atomic partial upsert
GET   /jobs/{job_id}/overrides          — raw legacy map (deterministic order)

Both exist only for READY_FOR_REVIEW in bounded G6 and share the manifest's
generic-404 identity policy (job ID only — a project ID yields 404). Other
states are a safe 409 job_not_editable; database failures roll back and
return a sanitized 503 persistence_unavailable. The original generated
scenes_json artifact is immutable — user edits live ONLY in scene_overrides.

v0.1 limitation (explicit): scene_id is validated for canonical SHAPE; a
canonical-but-nonexistent scene creates an orphan override rather than
triggering a per-PATCH S3 read of scenes.json. Semantics are honest
per-field last-write-wins — no optimistic locking.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain.states import JobState
from app.models import SceneOverride
from app.repositories.artifacts import load_job_with_project
from app.repositories.overrides import list_overrides, upsert_override
from app.schemas.scenes import SCENE_ID_RE, SceneOverridePatch

logger = logging.getLogger("app.scenes")
router = APIRouter()


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _load_editable(db: Session, job_id: str):
    try:
        parsed = uuid.UUID(job_id)
    except ValueError:
        raise _http_error(404, "not_found", "not found") from None
    try:
        row = load_job_with_project(db, parsed)
    except Exception:
        logger.warning("override_failed category=database")
        raise _http_error(503, "persistence_unavailable", "persistence unavailable") from None
    if row is None:  # absent job OR a project ID supplied as a job ID
        raise _http_error(404, "not_found", "not found")
    if row.Job.status != JobState.READY_FOR_REVIEW.value:
        raise _http_error(409, "job_not_editable", "job is not editable in its current state")
    return row


def _override_body(row: SceneOverride) -> dict[str, Any]:
    body: dict[str, Any] = {"active": row.active, "locked": row.locked}
    if row.text is not None:
        body["ad"] = row.text
    if row.voice is not None:
        body["voice"] = row.voice
    if row.speed is not None:
        body["speed"] = float(row.speed)
    return body


@router.patch("/jobs/{job_id}/scenes/{scene_id}")
def patch_scene(
    job_id: str, scene_id: str, payload: SceneOverridePatch, db: Session = Depends(get_db)
) -> dict[str, Any]:
    row = _load_editable(db, job_id)
    # G6.1: fullmatch — `.match()` with `$` accepts a trailing newline.
    if len(scene_id) > 120 or not SCENE_ID_RE.fullmatch(scene_id):
        raise _http_error(422, "invalid_scene_id", "scene id must be canonical (scene_N)")
    try:
        stored = upsert_override(db, row.Job.id, scene_id, payload.column_values())
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("override_failed category=database")
        raise _http_error(503, "persistence_unavailable", "persistence unavailable") from None
    return {
        "projectId": str(row.Project.id),
        "jobId": str(row.Job.id),
        "sceneId": stored.scene_id,
        "version": stored.version,
        "updatedAt": stored.updated_at.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "override": _override_body(stored),
    }


@router.get("/jobs/{job_id}/overrides")
def get_overrides(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    row = _load_editable(db, job_id)
    try:
        rows = list_overrides(db, row.Job.id)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("override_failed category=database")
        raise _http_error(503, "persistence_unavailable", "persistence unavailable") from None
    # The exact raw legacy map: no version/timestamps/IDs/wrapper metadata.
    # G6.1: private edit responses are never cached or stored.
    return JSONResponse(
        content={stored.scene_id: _override_body(stored) for stored in rows},
        headers={"Cache-Control": "private, no-store"},
    )
