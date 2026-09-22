"""Atomic claim with a per-claim ownership token (G5.1 A1) and token-guarded
updates.

`jobs.worker_id` stores a fresh cryptographically strong UUID generated for
EACH successful claim attempt — the fencing value. The configured worker name
is a human-readable log label only: task names can be reused, deployments can
overlap, and sequential attempts run under the same label, so a label can
never fence. Every progress, duration, retry, failure and success predicate
uses the exact claim token; a stale attempt (older token) can therefore never
update the row, delete the message on the row's behalf, or finalize.

Attempt counting happens exactly once per successful claim — PostgreSQL is
the application authority; SQS receive count is diagnostic only.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from app.domain.states import JobState
from app.models import Job
from sqlalchemy.orm import Session

from instascribe_worker.failures import FailureCode

CLAIMABLE = (JobState.QUEUED.value, JobState.UPLOAD_COMPLETE.value)


def new_claim_token() -> str:
    return str(uuid.uuid4())


def claim_job(
    session: Session,
    job_id: uuid.UUID,
    message_id: uuid.UUID,
    requested_at: datetime,
    *,
    provider: str | None = None,
) -> Job | None:
    """One conditional UPDATE … RETURNING on the COMPLETE message identity.
    On success the returned row's `worker_id` is this claim's fencing token."""
    token = new_claim_token()
    predicates = [
        Job.id == job_id,
        Job.enqueue_message_id == message_id,
        Job.enqueue_requested_at == requested_at,
        Job.status.in_(CLAIMABLE),
        Job.attempt_count < Job.max_attempts,
    ]
    if provider is not None:
        predicates.append(Job.provider == provider)
    stmt = (
        sa.update(Job)
        .where(*predicates)
        .values(
            status=JobState.PROCESSING.value,
            worker_id=token,
            attempt_count=Job.attempt_count + 1,
            started_at=sa.func.coalesce(Job.started_at, sa.func.now()),
            stage="initializing",
            progress=0,
            updated_at=sa.func.now(),
            error_code=None,
            error_message=None,
        )
        .returning(Job)
    )
    claimed = session.execute(stmt).scalar_one_or_none()
    session.commit()
    return claimed


def exhaust_unclaimable(
    session: Session,
    job_id: uuid.UUID,
    message_id: uuid.UUID,
    requested_at: datetime,
    *,
    provider: str | None = None,
) -> bool:
    """Durable FAILED/retry_exhausted for a delivery that can no longer claim.

    Atomically requires the job ID, the COMPLETE message identity, a still-
    claimable status AND `attempt_count >= max_attempts` — a row whose
    identity, state or attempt eligibility changed between observation and
    this UPDATE is left alone (rowcount honored by the caller)."""
    predicates = [
        Job.id == job_id,
        Job.enqueue_message_id == message_id,
        Job.enqueue_requested_at == requested_at,
        Job.status.in_(CLAIMABLE),
        Job.attempt_count >= Job.max_attempts,
    ]
    if provider is not None:
        predicates.append(Job.provider == provider)
    result = session.execute(
        sa.update(Job)
        .where(*predicates)
        .values(
            status=JobState.FAILED.value,
            error_code=FailureCode.RETRY_EXHAUSTED.value,
            error_message="processing attempts exhausted",
            worker_id=None,
            completed_at=sa.func.now(),
            updated_at=sa.func.now(),
        )
    )
    session.commit()
    return result.rowcount > 0


def guarded_update(session: Session, job_id: uuid.UUID, owner_token: str, **values) -> bool:
    """Update only while this claim's token still owns the PROCESSING row."""
    result = session.execute(
        sa.update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobState.PROCESSING.value,
            Job.worker_id == owner_token,
        )
        .values(updated_at=sa.func.now(), **values)
    )
    session.commit()
    return result.rowcount > 0


def guarded_transition(
    session: Session, job_id: uuid.UUID, owner_token: str, to_state: JobState, **values
) -> bool:
    """Move this claim's PROCESSING row to a new state; stale tokens no-op —
    a False return is OWNERSHIP LOSS, never success (G5.1 A3)."""
    result = session.execute(
        sa.update(Job)
        .where(
            Job.id == job_id,
            Job.status == JobState.PROCESSING.value,
            Job.worker_id == owner_token,
        )
        .values(status=to_state.value, updated_at=sa.func.now(), **values)
    )
    session.commit()
    return result.rowcount > 0
