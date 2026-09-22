import hashlib
import os
import sys
from pathlib import Path

import pytest

# Make `app` and the shared contracts importable when pytest runs from the
# repository root (the repo-root pyproject.toml wins rootdir detection).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parents[3] / "packages" / "contracts"))

# Test-environment defaults — documented placeholders only, set BEFORE any
# test module imports app.main. DATABASE_URL points at a closed port so unit
# tests never touch a real database (engines are lazy; 422 paths don't connect).
TEST_TOKEN = "test-token"
os.environ.setdefault("PORTFOLIO_TOKEN_SHA256", hashlib.sha256(TEST_TOKEN.encode()).hexdigest())
os.environ.setdefault("INSTASCRIBE_PIPELINE_REVISION", "test")
os.environ.setdefault("INSTASCRIBE_S3_ENDPOINT_PUBLIC", "http://localhost:4566")
os.environ.setdefault("INSTASCRIBE_S3_ENDPOINT_INTERNAL", "http://localhost:4566")
os.environ.setdefault("INSTASCRIBE_SQS_ENDPOINT_INTERNAL", "http://localhost:4566")
os.environ.setdefault("INSTASCRIBE_S3_FORCE_PATH_STYLE", "1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-2")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://placeholder:placeholder@127.0.0.1:59998/placeholder"
)

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_DB_URL = os.environ.get("INSTASCRIBE_TEST_DATABASE_URL")

requires_db = pytest.mark.skipif(
    not TEST_DB_URL,
    reason="INSTASCRIBE_TEST_DATABASE_URL not set (use `make cloud-test` or CI)",
)
requires_s3 = pytest.mark.skipif(
    not os.environ.get("INSTASCRIBE_TEST_S3"),
    reason="INSTASCRIBE_TEST_S3 not set (LocalStack required; use `make cloud-test` or CI)",
)

AUTH = {"X-Portfolio-Token": TEST_TOKEN}


@pytest.fixture(scope="session")
def safe_test_db_url():
    """Isolation gate + run-scoped disposable database.

    The guard refuses missing/ambiguous/retargeting/app-colliding URLs BEFORE
    any engine/Alembic/cleanup operation (db_isolation.py). Each suite run
    then creates its own uniquely named database so concurrent invocations
    cannot downgrade or delete each other's target; it is dropped in finally.
    """
    import sqlalchemy as sa
    from db_isolation import assert_safe_test_url, run_scoped_test_url
    from sqlalchemy.engine import make_url

    app_url = os.environ.get("DATABASE_URL")
    base = assert_safe_test_url(TEST_DB_URL, app_url)
    run_url = assert_safe_test_url(run_scoped_test_url(base), app_url)
    run_name = make_url(run_url).database

    admin = sa.create_engine(base, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{run_name}"'))
    admin.dispose()
    try:
        yield run_url
    finally:
        admin = sa.create_engine(base, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": run_name},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{run_name}"'))
        admin.dispose()


@pytest.fixture(scope="session")
def alembic_config(safe_test_db_url):
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    # The URL travels inside the Alembic config — the suite never redirects
    # the process-global DATABASE_URL at the application database's expense.
    cfg.set_main_option("sqlalchemy.url", safe_test_db_url)
    return cfg


@pytest.fixture(scope="session")
def migrated_db(alembic_config, safe_test_db_url):
    """Session-scoped: upgrade the DISPOSABLE test database to head; tear back
    to base. Destructive operations are scoped to the guarded test target only."""
    from alembic import command

    command.downgrade(alembic_config, "base")  # clean slate even after aborts
    command.upgrade(alembic_config, "head")
    yield safe_test_db_url
    command.downgrade(alembic_config, "base")


@pytest.fixture()
def db_engine(migrated_db):
    import sqlalchemy as sa

    engine = sa.create_engine(migrated_db)
    # Per-test isolation: children first, then jobs, then projects.
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM scene_overrides"))
        conn.execute(sa.text("DELETE FROM artifacts"))
        conn.execute(sa.text("DELETE FROM jobs"))
        conn.execute(sa.text("DELETE FROM projects"))
    yield engine
    engine.dispose()


@pytest.fixture()
def api_db_client(db_engine, migrated_db, monkeypatch):
    """TestClient whose app engine points at the migrated test database."""
    from app.core.config import get_settings
    from app.db.session import reset_engine_caches
    from app.main import app
    from app.services.s3 import reset_s3_caches
    from app.services.sqs import reset_sqs_caches
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DATABASE_URL", migrated_db)
    get_settings.cache_clear()
    reset_engine_caches()
    reset_s3_caches()
    reset_sqs_caches()
    yield TestClient(app)
    get_settings.cache_clear()
    reset_engine_caches()
    reset_s3_caches()
    reset_sqs_caches()


def _sqs_client():
    import boto3

    return boto3.client(
        "sqs",
        region_name=os.environ["AWS_DEFAULT_REGION"],
        endpoint_url=os.environ["INSTASCRIBE_SQS_ENDPOINT_INTERNAL"],
    )


from queue_support import make_queue_pair  # noqa: E402  (shared with the worker suite)


@pytest.fixture(scope="session")
def run_queue_pair():
    """Session-scoped RUN-OWNED queue pair (namespaced per invocation) —
    tests never create, configure, drain, or delete the development queue.
    Dropped in finally so failed runs still clean up."""
    import secrets

    client = _sqs_client()
    base_name = f"instascribe-test-{os.getpid()}-{secrets.token_hex(3)}-work"
    queue_url, dlq_url = make_queue_pair(client, base_name)
    try:
        yield queue_url, dlq_url, client
    finally:
        for url in (queue_url, dlq_url):
            try:
                client.delete_queue(QueueUrl=url)
            except Exception:
                pass  # preserve evidence; stale run-queues are namespaced anyway


@pytest.fixture()
def work_queue(run_queue_pair, monkeypatch):
    """Point the API-under-test at the run-owned queue and drain ONLY it."""
    from app.services.sqs import reset_sqs_caches

    queue_url, _dlq_url, client = run_queue_pair
    monkeypatch.setenv("INSTASCRIBE_WORK_QUEUE_URL", queue_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_sqs_caches()
    while True:
        messages = client.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=0
        ).get("Messages", [])
        if not messages:
            break
        for message in messages:
            client.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
    yield queue_url, client
    get_settings.cache_clear()
    reset_sqs_caches()


@pytest.fixture()
def media_bucket():
    """Ensure the media bucket exists with BPA + default encryption (idempotent;
    lets CI run without the compose ready.d bootstrap)."""
    import boto3

    client = boto3.client(
        "s3",
        region_name=os.environ["AWS_DEFAULT_REGION"],
        endpoint_url=os.environ["INSTASCRIBE_S3_ENDPOINT_INTERNAL"],
    )
    bucket = os.environ.get("INSTASCRIBE_MEDIA_BUCKET", "instascribe-media")
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(
            Bucket=bucket,
            CreateBucketConfiguration={"LocationConstraint": os.environ["AWS_DEFAULT_REGION"]},
        )
        client.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        client.put_bucket_encryption(
            Bucket=bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            },
        )
    # Versioning is REQUIRED (G5.1 C1) — idempotent, applied even when the
    # bucket pre-exists so older local stacks converge.
    client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    return bucket, client
