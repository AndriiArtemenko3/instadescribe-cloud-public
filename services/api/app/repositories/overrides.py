"""Atomic scene-override persistence (G6 Gate 3, ADR-0002).

ONE PostgreSQL `INSERT ... ON CONFLICT (job_id, scene_id) DO UPDATE`:
an insert starts at version 1 (server default); an accepted conflict update
touches ONLY the fields present in this request, never resets omitted fields
and explicitly sets `updated_at = now()` and `version = version + 1` — ORM
onupdate is NOT relied upon for the Core upsert. Concurrency is honest
per-field last-write-wins; no client version or optimistic-lock 409 in v0.1.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import SceneOverride


def upsert_override(
    session: Session, job_id: uuid.UUID, scene_id: str, column_values: dict
) -> SceneOverride:
    """Apply one strict partial update atomically; returns the stored row."""
    stmt = pg_insert(SceneOverride).values(
        id=uuid.uuid4(), job_id=job_id, scene_id=scene_id, **column_values
    )
    table = SceneOverride.__table__
    set_ = {name: stmt.excluded[name] for name in column_values}
    set_["updated_at"] = sa.func.now()
    set_["version"] = table.c.version + 1
    stmt = stmt.on_conflict_do_update(index_elements=["job_id", "scene_id"], set_=set_).returning(
        SceneOverride
    )
    row = session.execute(stmt).scalar_one()
    session.commit()
    return row


def list_overrides(session: Session, job_id: uuid.UUID) -> list[SceneOverride]:
    """Deterministic order: numeric scene order for canonical IDs
    (length-then-lexicographic sorts scene_2 before scene_10)."""
    return list(
        session.execute(
            sa.select(SceneOverride)
            .where(SceneOverride.job_id == job_id)
            .order_by(sa.func.length(SceneOverride.scene_id), SceneOverride.scene_id)
        ).scalars()
    )
