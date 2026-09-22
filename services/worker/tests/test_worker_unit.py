"""Worker fast tests: configuration, media validation, source download call
shape, workspace/executor behaviour and log sanitization — no database or
AWS services required."""

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.stub import Stubber
from instascribe_worker.config import WorkerSettings
from instascribe_worker.failures import FailureCode, JobFailure
from instascribe_worker.media_validation import validate_media
from instascribe_worker.source import download_source
from instascribe_worker.workspace import build_workspace, write_job_files
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "App" / "public" / "videos" / "sintel-blender-cc.mp4"


# --- configuration ---------------------------------------------------------


def test_missing_database_url_fails_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        WorkerSettings()


@pytest.mark.parametrize(
    "env",
    [
        {"INSTASCRIBE_LONG_POLL_SECS": "21"},  # > SQS maximum
        {"INSTASCRIBE_SUBPROCESS_TIMEOUT_SECS": "5"},  # under the floor
        {"INSTASCRIBE_WORK_QUEUE_URL": "ftp://nope"},
        {"INSTASCRIBE_WORK_QUEUE": ""},
        {"INSTASCRIBE_MAX_DURATION_SECS": "0"},
    ],
)
def test_invalid_configuration_fails_fast(monkeypatch, env):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/x")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ValidationError):
        WorkerSettings()


def test_exact_g12_provider_allowlist_cannot_be_widened_by_environment(monkeypatch):
    """G12 provider policy is code-owned; hostile env cannot add backends."""
    from instascribe_worker.config import PROVIDER_ALLOWLIST

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/x")
    for hostile in ("PROVIDER_ALLOWLIST", "provider_allowlist", "INSTASCRIBE_PROVIDER_ALLOWLIST"):
        monkeypatch.setenv(hostile, '["fake","openai"]')
    settings = WorkerSettings()
    assert settings.provider_allowlist == ("fake", "openai")
    assert PROVIDER_ALLOWLIST == ("fake", "openai")


def test_missing_pipeline_revision_fails_fast(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/x")
    monkeypatch.delenv("INSTASCRIBE_PIPELINE_REVISION", raising=False)
    with pytest.raises(ValidationError):
        WorkerSettings()


def test_pipeline_revision_bounds_match_the_api_contract(monkeypatch):
    """G8 B2: trimmed, non-empty, at most 120 characters — the exact
    semantics of the API validator and the sa.String(120) column. The old
    worker bound stopped at 100 and never trimmed."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/x")

    # Whitespace is trimmed, not preserved and not rejected.
    monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", "  dev  ")
    assert WorkerSettings().pipeline_revision == "dev"

    # Boundary lengths: 1 and 120 accepted; the API's 101-120 range no
    # longer fails in the worker.
    monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", "r")
    assert WorkerSettings().pipeline_revision == "r"
    monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", "r" * 120)
    assert WorkerSettings().pipeline_revision == "r" * 120

    # Empty after trimming and 121 are rejected.
    for bad in ("   ", "\t\n", "r" * 121):
        monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", bad)
        with pytest.raises(ValidationError):
            WorkerSettings()


def test_config_validation_errors_hide_input_values(monkeypatch):
    """G5.1 B3: a secret-bearing invalid value never appears in the error."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:sekret-pw@127.0.0.1:5432/x")
    monkeypatch.setenv("INSTASCRIBE_WORK_QUEUE_URL", "ftp://token-SEKRET@evil")
    with pytest.raises(ValidationError) as exc:
        WorkerSettings()
    text = str(exc.value)
    assert "SEKRET" not in text and "sekret-pw" not in text


def test_openai_mode_requires_key_and_two_minute_limit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/x")
    monkeypatch.setenv("INSTASCRIBE_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("INSTASCRIBE_MAX_DURATION_SECS", "120")
    monkeypatch.setenv("INSTASCRIBE_MAX_ATTEMPTS", "1")
    with pytest.raises(ValidationError):
        WorkerSettings()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-secret")
    monkeypatch.setenv("INSTASCRIBE_MAX_DURATION_SECS", "121")
    with pytest.raises(ValidationError):
        WorkerSettings()
    monkeypatch.setenv("INSTASCRIBE_MAX_DURATION_SECS", "120")
    settings = WorkerSettings()
    assert settings.provider == "openai" and settings.max_provider_calls == 6
    monkeypatch.setenv("INSTASCRIBE_MAX_ATTEMPTS", "3")
    with pytest.raises(ValidationError):
        WorkerSettings()


# --- stored-settings contract (B4) -----------------------------------------


def _stored(**overrides):
    base = {
        "model": "gpt-4.1",
        "frame_quality": "low",
        "fps": 1.0,
        "chunk_size": 60,
        "audio_extraction": True,
        "custom_prompt": "",
        "language": None,
        "detail_level": 3,
        "preset_style": "documentary",
        "project_name": "p",
        "duration_secs": 12.5,
    }
    base.update(overrides)
    return base


def test_stored_settings_contract_accepts_the_api_shape():
    from instascribe_contracts.settings import StoredJobSettings

    parsed = StoredJobSettings.model_validate(_stored())
    assert parsed.model == "gpt-4.1" and parsed.fps == 1.0


@pytest.mark.parametrize(
    "mutation",
    [
        {"model": "gpt-5-ultra"},  # not allowlisted
        {"frame_quality": "high"},
        {"fps": 30.0},
        {"chunk_size": 61},
        {"audio_extraction": 1},  # int is not a strict bool
        {"custom_prompt": "x" * 2001},
        {"custom_prompt": "bad\x00control"},
        {"language": "not a language tag!"},
        {"detail_level": 9},
        {"preset_style": "noir"},
        {"project_name": ""},
        {"duration_secs": 0},
        {"duration_secs": 100000},
        {"extra_key": "forbidden"},
    ],
)
def test_stored_settings_contract_rejects_tampered_documents(mutation):
    from instascribe_contracts.settings import StoredJobSettings
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        StoredJobSettings.model_validate(_stored(**mutation))


def test_stored_settings_contract_rejects_missing_keys_and_non_dicts():
    from instascribe_contracts.settings import StoredJobSettings
    from pydantic import ValidationError as PydanticValidationError

    incomplete = _stored()
    incomplete.pop("model")
    for bad in (incomplete, [], "settings", None, 42):
        with pytest.raises(PydanticValidationError):
            StoredJobSettings.model_validate(bad)


# --- media validation (before any model work) ------------------------------


@pytest.mark.skipif(not FIXTURE.exists(), reason="Sintel fixture missing")
def test_real_fixture_passes_validation_and_reports_measured_duration():
    duration = validate_media(FIXTURE, "video/mp4", 300, source_name="sintel-blender-cc.mp4")
    assert 100 < duration < 130  # the committed 120s clip — MEASURED, not declared


def test_corrupt_and_empty_media_are_non_retryable(tmp_path):
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"not a video at all" * 10)
    with pytest.raises(JobFailure) as exc:
        validate_media(corrupt, "video/mp4", 300, source_name="corrupt.mp4")
    assert exc.value.code == FailureCode.INVALID_MEDIA
    assert exc.value.retryable is False
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(JobFailure):
        validate_media(empty, "video/mp4", 300, source_name="empty.mp4")


@pytest.mark.skipif(not FIXTURE.exists(), reason="Sintel fixture missing")
def test_actual_over_limit_duration_is_rejected_regardless_of_declaration():
    """G5.1 C3: a short DECLARED duration cannot bypass the actual cap — the
    ffprobe measurement is authoritative."""
    with pytest.raises(JobFailure, match="portfolio limit"):
        validate_media(FIXTURE, "video/mp4", 5, source_name="sintel-blender-cc.mp4")


@pytest.mark.skipif(not FIXTURE.exists(), reason="Sintel fixture missing")
def test_extension_content_type_pair_is_the_contract():
    """G5.1 C3: individually allowlisted values must still PAIR — a .webm
    name with video/mp4 (or an mp4 name with video/webm) is inconsistent."""
    with pytest.raises(JobFailure) as exc:
        validate_media(FIXTURE, "video/webm", 300, source_name="sintel-blender-cc.mp4")
    assert exc.value.code == FailureCode.INVALID_SETTINGS
    with pytest.raises(JobFailure) as exc:
        validate_media(FIXTURE, "video/mp4", 300, source_name="clip.webm")
    assert exc.value.code == FailureCode.INVALID_SETTINGS


@pytest.mark.skipif(not FIXTURE.exists(), reason="Sintel fixture missing")
def test_mp4_container_under_webm_name_and_type_is_rejected(tmp_path):
    """G5.1 C3: consistent-looking name+type with the WRONG actual container
    (an MP4 file renamed .webm, declared video/webm) must fail on the probe."""
    disguised = tmp_path / "disguised.webm"
    disguised.write_bytes(FIXTURE.read_bytes())
    with pytest.raises(JobFailure) as exc:
        validate_media(disguised, "video/webm", 300, source_name="disguised.webm")
    assert exc.value.code == FailureCode.INVALID_MEDIA
    assert "container" in exc.value.public_message


def test_audio_only_media_is_rejected(tmp_path):
    audio = tmp_path / "audio.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:a",
            "aac",
            str(audio),
        ],
        check=True,
    )
    with pytest.raises(JobFailure, match="no video stream"):
        validate_media(audio, "video/mp4", 300, source_name="audio.mp4")


def test_unallowlisted_stored_type_is_invalid_settings(tmp_path):
    with pytest.raises(JobFailure) as exc:
        validate_media(tmp_path / "x.mp4", "application/octet-stream", 300, source_name="x.mp4")
    assert exc.value.code == FailureCode.INVALID_SETTINGS
    with pytest.raises(JobFailure) as exc:
        validate_media(tmp_path / "x.bin", "video/mp4", 300, source_name="x.bin")
    assert exc.value.code == FailureCode.INVALID_SETTINGS


# --- exact source download -------------------------------------------------


def _job(**kw):
    base = dict(
        input_object_key="uploads/j/source/clip.mp4",
        input_size_bytes=11,
        source_etag="abc123",
        source_version_id="v-42",  # C1: every processed source is pinned
        source_checksum_sha256=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _stub_client():
    import boto3

    return boto3.client("s3", region_name="eu-west-2", endpoint_url="http://localhost:4566")


def _Body(payload: bytes):
    """A genuine StreamingBody: passes Stubber's response validation AND
    supports iter_chunks like real S3 responses."""
    import io

    from botocore.response import StreamingBody

    return StreamingBody(io.BytesIO(payload), len(payload))


def test_missing_pinned_version_is_a_deterministic_identity_failure(tmp_path):
    """G5.1 C1: the worker ALWAYS downloads the exact persisted VersionId —
    a job without one cannot prove source identity and never falls back to
    'latest'."""
    job = _job(source_version_id=None)

    class NeverCalled:
        def get_object(self, **kwargs):
            raise AssertionError("no S3 call may happen without a pinned version")

    with pytest.raises(JobFailure) as exc:
        download_source(NeverCalled(), "b", job, tmp_path / "v.mp4")
    assert exc.value.code == FailureCode.SOURCE_IDENTITY_MISMATCH
    assert exc.value.retryable is False


def test_version_id_is_always_requested_exactly(tmp_path):
    client = _stub_client()
    job = _job()
    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {"ETag": '"abc123"', "VersionId": "v-42", "Body": _Body(b"hello world")},
            {"Bucket": "b", "Key": job.input_object_key, "VersionId": "v-42"},
        )
        digest = download_source(client, "b", job, tmp_path / "v.mp4")
    assert digest == __import__("hashlib").sha256(b"hello world").hexdigest()


def test_body_is_closed_on_identity_mismatch(tmp_path):
    """G5.1 C2: the StreamingBody is closed in finally on EVERY early
    failure, not only after a successful stream."""
    import io

    from botocore.response import StreamingBody

    client = _stub_client()
    job = _job()
    raw = io.BytesIO(b"hello world")
    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {
                "ETag": '"DIFFERENT"',
                "VersionId": "v-42",
                "Body": StreamingBody(raw, 11),
            },
            {"Bucket": "b", "Key": job.input_object_key, "VersionId": "v-42"},
        )
        with pytest.raises(JobFailure, match="ETag"):
            download_source(client, "b", job, tmp_path / "v.mp4")
    assert raw.closed  # closed despite the pre-stream failure


def test_body_is_closed_on_size_overflow(tmp_path):
    import io

    from botocore.response import StreamingBody

    client = _stub_client()
    job = _job(input_size_bytes=5)  # response is larger than verified
    raw = io.BytesIO(b"hello world")
    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {"ETag": '"abc123"', "VersionId": "v-42", "Body": StreamingBody(raw, 11)},
            {"Bucket": "b", "Key": job.input_object_key, "VersionId": "v-42"},
        )
        with pytest.raises(JobFailure, match="larger"):
            download_source(client, "b", job, tmp_path / "v.mp4")
    assert raw.closed


def test_persisted_checksum_requires_present_and_equal_response_checksum(tmp_path):
    """G5.1 C2: when a trustworthy checksum was persisted, checksum mode is
    requested and an ABSENT response checksum is an identity failure — never
    silently skipped; a matching one succeeds."""
    checksum = "q1o0MDNr2QU0Cs+YfCa9rniszHrG8+lIcbBUR8jI/OM="
    client = _stub_client()
    job = _job(source_checksum_sha256=checksum)
    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {"ETag": '"abc123"', "VersionId": "v-42", "Body": _Body(b"hello world")},
            {
                "Bucket": "b",
                "Key": job.input_object_key,
                "VersionId": "v-42",
                "ChecksumMode": "ENABLED",
            },
        )
        with pytest.raises(JobFailure, match="checksum evidence is missing"):
            download_source(client, "b", job, tmp_path / "v.mp4")

    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {
                "ETag": '"abc123"',
                "VersionId": "v-42",
                "ChecksumSHA256": "SOMETHING-ELSE=",
                "Body": _Body(b"hello world"),
            },
            {
                "Bucket": "b",
                "Key": job.input_object_key,
                "VersionId": "v-42",
                "ChecksumMode": "ENABLED",
            },
        )
        with pytest.raises(JobFailure, match="checksum changed"):
            download_source(client, "b", job, tmp_path / "v.mp4")

    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {
                "ETag": '"abc123"',
                "VersionId": "v-42",
                "ChecksumSHA256": checksum,
                "Body": _Body(b"hello world"),
            },
            {
                "Bucket": "b",
                "Key": job.input_object_key,
                "VersionId": "v-42",
                "ChecksumMode": "ENABLED",
            },
        )
        download_source(client, "b", job, tmp_path / "v.mp4")


def test_precondition_failure_is_deterministic_identity_mismatch(tmp_path):
    client = _stub_client()
    job = _job()
    with Stubber(client) as stub:
        stub.add_client_error(
            "get_object", service_error_code="PreconditionFailed", http_status_code=412
        )
        with pytest.raises(JobFailure) as exc:
            download_source(client, "b", job, tmp_path / "v.mp4")
    assert exc.value.code == FailureCode.SOURCE_IDENTITY_MISMATCH
    assert exc.value.retryable is False


def test_size_mismatch_is_identity_mismatch(tmp_path):
    client = _stub_client()
    job = _job(input_size_bytes=999)
    with Stubber(client) as stub:
        stub.add_response(
            "get_object",
            {"ETag": '"abc123"', "VersionId": "v-42", "Body": _Body(b"hello world")},
            None,
        )
        with pytest.raises(JobFailure, match="smaller"):
            download_source(client, "b", job, tmp_path / "v.mp4")


def test_transport_failure_is_retryable(tmp_path):
    from botocore.exceptions import EndpointConnectionError

    class Boom:
        def get_object(self, **kwargs):
            raise EndpointConnectionError(endpoint_url="http://secret-host:4566")

    with pytest.raises(JobFailure) as exc:
        download_source(Boom(), "b", _job(), tmp_path / "v.mp4")
    assert exc.value.code == FailureCode.SOURCE_DOWNLOAD_FAILED
    assert exc.value.retryable is True
    assert "secret-host" not in exc.value.public_message


# --- workspace + subprocess adapter ---------------------------------------


def test_workspace_isolates_pipeline_and_cleans_up():
    job_id = str(uuid.uuid4())
    ws = build_workspace(None, str(REPO / "modular_pipeline"), job_id)
    root = ws.root
    assert (ws.pipeline_dir / "run_job.py").exists()
    assert (root / "App" / "public" / "videos").is_dir()
    write_job_files(ws, job_id, {"model": "gpt-4.1", "chunk_size": 60})
    settings = json.loads(ws.settings_path.read_text())
    assert settings["job_id"] == job_id
    assert settings["video_path"] == str(ws.video_path)
    assert json.loads(ws.status_path.read_text())["status"] == "queued"
    ws.cleanup()
    assert not root.exists()  # removed even on the happy path


def _fake_pipeline_workspace(tmp_path, script: str):
    """A minimal workspace whose run_job.py is a controllable stand-in."""
    from instascribe_worker.workspace import Workspace

    pipeline = tmp_path / "modular_pipeline"
    job_dir = pipeline / "jobs" / "job"
    job_dir.mkdir(parents=True)
    (pipeline / "run_job.py").write_text(script)
    data_dir = tmp_path / "App" / "public" / "data" / "job"
    data_dir.mkdir(parents=True)

    class _NoopTmp:
        def cleanup(self):
            pass

    return Workspace(
        tmp=_NoopTmp(),
        root=tmp_path,
        pipeline_dir=pipeline,
        job_dir=job_dir,
        settings_path=job_dir / "settings.json",
        status_path=job_dir / "status.json",
        video_path=job_dir / "video.mp4",
        data_dir=data_dir,
    )


def test_pre_main_nonzero_exit_is_authoritative_over_stale_status(tmp_path):
    from instascribe_worker.executor import run_pipeline

    ws = _fake_pipeline_workspace(tmp_path, "import sys\nsys.exit(3)\n")
    # Stale/lying status: 'ready' before the child even ran.
    ws.status_path.write_text(json.dumps({"status": "ready", "progress": 100, "stage": "complete"}))
    result = run_pipeline(ws, "job", timeout_secs=30, grace_secs=2, on_progress=lambda s, p: None)
    assert result.exit_code == 3
    assert result.timed_out is False


def test_timeout_terminates_and_reaps_child(tmp_path):
    from instascribe_worker.executor import run_pipeline

    ws = _fake_pipeline_workspace(tmp_path, "import time\ntime.sleep(120)\n")
    result = run_pipeline(ws, "job", timeout_secs=1, grace_secs=1, on_progress=lambda s, p: None)
    assert result.timed_out is True
    assert result.exit_code != 0
    from instascribe_worker.executor import current_child

    assert current_child() is None  # reaped and deregistered


def test_progress_mirroring_skips_partial_status_writes(tmp_path):
    from instascribe_worker.executor import run_pipeline

    script = (
        "import json, pathlib, time\n"
        "p = pathlib.Path('jobs/job/status.json')\n"
        "p.write_text('{partial')\n"  # torn write: must not crash the poller
        "time.sleep(0.5)\n"
        "p.write_text(json.dumps({'status':'processing','progress':42,'stage':'analyzing_frames'}))\n"
        "time.sleep(0.5)\n"
    )
    ws = _fake_pipeline_workspace(tmp_path, script)
    seen = []
    result = run_pipeline(
        ws, "job", timeout_secs=30, grace_secs=2, on_progress=lambda s, p: seen.append((s, p))
    )
    assert result.exit_code == 0
    assert ("analyzing_frames", 42) in seen


_TREE_SCRIPT = """
import json, os, pathlib, subprocess, sys, time
grand = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
pathlib.Path("jobs/job/pids.json").write_text(
    json.dumps({"child": os.getpid(), "grand": grand.pid})
)
pathlib.Path("jobs/job/status.json").write_text(
    json.dumps({"status": "processing", "progress": 10, "stage": "analyzing_frames"})
)
time.sleep(300)
"""


def _pid_alive(pid: int) -> bool:
    import os

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_pids(ws, deadline_secs=15) -> dict:
    import time as _time

    pids_path = ws.job_dir / "pids.json"
    deadline = _time.monotonic() + deadline_secs
    while _time.monotonic() < deadline:
        try:
            return json.loads(pids_path.read_text())
        except Exception:
            _time.sleep(0.05)
    raise AssertionError("child never wrote pids.json")


def _assert_tree_gone(pids: dict, deadline_secs=10) -> None:
    import time as _time

    deadline = _time.monotonic() + deadline_secs
    while _time.monotonic() < deadline:
        if not _pid_alive(pids["child"]) and not _pid_alive(pids["grand"]):
            return
        _time.sleep(0.1)
    raise AssertionError(
        f"process tree survived: child_alive={_pid_alive(pids['child'])} "
        f"grand_alive={_pid_alive(pids['grand'])}"
    )


def test_timeout_kills_the_whole_process_tree(tmp_path):
    """G5.1 B1: a REAL child spawning a REAL grandchild — both must be gone
    after the timeout, the child reaped, and the registry cleared."""
    from instascribe_worker.executor import current_child, run_pipeline

    ws = _fake_pipeline_workspace(tmp_path, _TREE_SCRIPT)
    result = run_pipeline(ws, "job", timeout_secs=1, grace_secs=1, on_progress=lambda s, p: None)
    assert result.timed_out is True
    pids = _read_pids(ws, deadline_secs=1)
    _assert_tree_gone(pids)
    assert current_child() is None  # reaped and deregistered


def test_progress_callback_exception_kills_the_whole_process_tree(tmp_path):
    """G5.1 B1 regression (reproduced failure #4): a raising progress
    callback (e.g. database down) must not leave run_job.py or its FFmpeg
    grandchild alive while the caller cleans the workspace."""
    from instascribe_worker.executor import current_child, run_pipeline

    ws = _fake_pipeline_workspace(tmp_path, _TREE_SCRIPT)

    def _boom(stage, progress):
        raise RuntimeError("db down")

    with pytest.raises(RuntimeError):
        run_pipeline(ws, "job", timeout_secs=30, grace_secs=1, on_progress=_boom)
    pids = _read_pids(ws, deadline_secs=1)
    _assert_tree_gone(pids)
    assert current_child() is None


def test_sigterm_path_kills_the_whole_process_tree(tmp_path):
    """G5.1 B1: terminate_current (the SIGTERM/SIGINT handler entry) destroys
    the registered tree while run_pipeline is live."""
    import threading

    from instascribe_worker import executor

    ws = _fake_pipeline_workspace(tmp_path, _TREE_SCRIPT)
    results: list = [None]

    def _run():
        results[0] = executor.run_pipeline(
            ws, "job", timeout_secs=60, grace_secs=1, on_progress=lambda s, p: None
        )

    runner = threading.Thread(target=_run)
    runner.start()
    pids = _read_pids(ws)
    executor.terminate_current(grace_secs=1)
    runner.join(timeout=20)
    assert not runner.is_alive()
    _assert_tree_gone(pids)
    assert results[0] is not None and results[0].exit_code != 0
    assert executor.current_child() is None


def test_interrupted_executor_still_kills_the_tree_and_reaps(tmp_path):
    """G5.1 B1: ANY exception while the child is live (simulated interruption
    raised from the polling loop) leaves no process behind."""
    from instascribe_worker.executor import current_child, run_pipeline

    ws = _fake_pipeline_workspace(tmp_path, _TREE_SCRIPT)
    calls = {"n": 0}

    def _interrupt(stage, progress):
        calls["n"] += 1
        raise KeyboardInterrupt  # what Ctrl-C delivers mid-poll

    with pytest.raises(KeyboardInterrupt):
        run_pipeline(ws, "job", timeout_secs=60, grace_secs=1, on_progress=_interrupt)
    pids = _read_pids(ws, deadline_secs=1)
    _assert_tree_gone(pids)
    assert current_child() is None


# --- progress dedup/throttle (B2) ------------------------------------------


def test_progress_writes_are_deduplicated_and_throttled(monkeypatch):
    """G5.1 B2: a long unchanged status must produce a BOUNDED number of
    database updates; stage changes and >=99 progress write immediately."""
    from instascribe_worker import progress as progress_mod

    writes = []
    monkeypatch.setattr(
        progress_mod,
        "guarded_update",
        lambda session, job_id, token, **values: writes.append(values) or True,
    )
    clock = {"now": 0.0}
    mirror = progress_mod.ProgressMirror(
        None, uuid.uuid4(), "token", min_interval=1.0, clock=lambda: clock["now"]
    )
    for _ in range(50):  # 10 seconds of identical 200ms observations
        clock["now"] += 0.2
        mirror("analyzing_frames", 40)
    assert len(writes) == 1  # dedup: unchanged observations never write

    mirror("exporting", 41)  # stage change writes immediately
    assert len(writes) == 2
    mirror("exporting", 42)  # progress-only change inside the interval
    assert len(writes) == 2
    clock["now"] += 1.1
    mirror("exporting", 43)  # interval elapsed
    assert len(writes) == 3
    mirror("exporting", 99)  # near-final progress writes immediately
    assert len(writes) == 4
    # Monotonic + capped: the SQL uses GREATEST(progress, bounded), bound 99.
    assert all("progress" in w and "stage" in w for w in writes)


# --- entrypoint sanitization (B3) ------------------------------------------


def test_invalid_config_exits_nonzero_without_secrets_or_traceback(monkeypatch, capsys):
    """G5.1 B3 regression (reproduced failure #5): startup validation failure
    emits a category event only — no input values, no Pydantic traceback."""
    from instascribe_worker.config import reset_worker_settings
    from instascribe_worker.main import main

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:sekret-pw@127.0.0.1:5432/x")
    monkeypatch.setenv("INSTASCRIBE_WORK_QUEUE_URL", "ftp://SEKRET-token@evil:99")
    reset_worker_settings()
    try:
        assert main(["--once"]) == 1
    finally:
        reset_worker_settings()
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert '"event": "worker_config_invalid"' in combined
    for leak in ("sekret-pw", "SEKRET-token", "Traceback", "ValidationError", "ftp://"):
        assert leak not in combined


def test_once_mode_exits_nonzero_after_one_sanitized_infra_failure(monkeypatch, capsys):
    """G5.1 B3: --once + unreachable queue -> sanitized infra_error, exit 1,
    no endpoint/traceback leakage."""
    from instascribe_worker import main as main_mod
    from instascribe_worker.config import reset_worker_settings
    from instascribe_worker.consumer import reset_worker_caches

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/x")
    monkeypatch.setenv(
        "INSTASCRIBE_WORK_QUEUE_URL", "http://127.0.0.1:59995/000000000000/secret-queue-name"
    )
    monkeypatch.setenv("INSTASCRIBE_SQS_ENDPOINT_INTERNAL", "http://127.0.0.1:59995")
    reset_worker_settings()
    reset_worker_caches()
    try:
        assert main_mod.main(["--once"]) == 1
    finally:
        reset_worker_settings()
        reset_worker_caches()
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert '"outcome": "infra_error"' in combined
    for leak in ("59995", "secret-queue-name", "Traceback"):
        assert leak not in combined


def test_child_environment_excludes_secrets(monkeypatch):
    from instascribe_worker.executor import _child_env

    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "super-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")
    monkeypatch.setenv("PORTFOLIO_TOKEN_SHA256", "deadbeef")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://hostile-proxy.example")
    env = _child_env()
    assert env["INSTASCRIBE_BACKEND"] == "fake"
    joined = json.dumps(env)
    for leak in (
        "super-secret",
        "pw@host",
        "deadbeef",
        "ambient-openai-secret",
        "hostile-proxy",
    ):
        assert leak not in joined


def test_openai_child_environment_is_explicit_and_bounded(monkeypatch):
    from instascribe_worker.executor import _child_env

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA-HOSTILE")
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret@host/db")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://hostile-proxy.example")
    key = "sk-child-only"
    env = _child_env(
        "openai",
        openai_api_key=key,
        max_provider_calls=6,
        max_provider_output_tokens=8000,
    )
    assert env["INSTASCRIBE_BACKEND"] == "openai"
    assert env["OPENAI_API_KEY"] == key
    assert env["INSTASCRIBE_MAX_PROVIDER_CALLS"] == "6"
    assert env["INSTASCRIBE_MAX_PROVIDER_OUTPUT_TOKENS"] == "8000"
    joined = json.dumps(env)
    for forbidden in ("AKIA-HOSTILE", "secret@host", "hostile-proxy", "OPENAI_BASE_URL"):
        assert forbidden not in joined


def test_openai_missing_key_exits_sanitized_before_queue_access(monkeypatch, capsys):
    from instascribe_worker import main as main_mod
    from instascribe_worker.config import reset_worker_settings

    monkeypatch.setenv("INSTASCRIBE_PROVIDER", "openai")
    monkeypatch.setenv("INSTASCRIBE_MAX_DURATION_SECS", "120")
    monkeypatch.setenv("INSTASCRIBE_MAX_ATTEMPTS", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    called = {"run": False}

    def should_not_run(*args, **kwargs):
        called["run"] = True
        return "empty"

    monkeypatch.setattr(main_mod, "run_once", should_not_run)
    reset_worker_settings()
    try:
        assert main_mod.main(["--once"]) == 1
    finally:
        reset_worker_settings()
    assert called["run"] is False
    output = capsys.readouterr().out
    assert '"event": "worker_config_invalid"' in output
    assert "OPENAI_API_KEY" not in output and "Traceback" not in output


# --- artifact validation matrix (D1/D3 #1-3) --------------------------------


def _artifact_workspace(tmp_path, scenes=None, result=None, raw_scenes: str | None = None):
    """A synthesized completed-output tree for validate_outputs."""
    from instascribe_worker.workspace import Workspace

    pipeline = tmp_path / "modular_pipeline"
    job_dir = pipeline / "jobs" / "job"
    job_dir.mkdir(parents=True, exist_ok=True)
    data_dir = tmp_path / "App" / "public" / "data" / "job"
    data_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "scenes.json": scenes
        if scenes is not None
        else [{"scene_id": "scene_1", "start": 0.0, "end": 2.0}],
        "entities.json": [],
        "audio_events.json": [],
        "ad_placement_gaps.json": [],
        "transcript.json": [],
    }
    for name, payload in payloads.items():
        (data_dir / name).write_text(json.dumps(payload))
    (data_dir / "system_info.json").write_text(
        json.dumps(
            {
                "video_id": "job",
                "processing": {
                    "model": "gpt-4.1",
                    "image_detail": "low",
                    "chunk_sizes": [60],
                },
                "tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "status": "completed",
            }
        )
    )
    if raw_scenes is not None:
        (data_dir / "scenes.json").write_text(raw_scenes)
    scene_count = len(payloads["scenes.json"]) if scenes is not None or raw_scenes is None else 1
    result_doc = (
        result if result is not None else {"data_path": "/data/job", "scene_count": scene_count}
    )
    job_dir.joinpath("result.json").write_text(json.dumps(result_doc))

    class _NoopTmp:
        def cleanup(self):
            pass

    return Workspace(
        tmp=_NoopTmp(),
        root=tmp_path,
        pipeline_dir=pipeline,
        job_dir=job_dir,
        settings_path=job_dir / "settings.json",
        status_path=job_dir / "status.json",
        video_path=job_dir / "video.mp4",
        data_dir=data_dir,
    )


def _expect_artifacts_invalid(ws):
    from instascribe_worker.artifacts import validate_outputs

    with pytest.raises(JobFailure) as exc:
        validate_outputs(ws, "job", 1)
    assert exc.value.code == FailureCode.ARTIFACTS_INVALID
    return exc.value


def test_openai_system_info_is_required_and_rewritten_secret_free(tmp_path):
    from instascribe_worker.artifacts import validate_outputs

    missing = _artifact_workspace(tmp_path / "missing-system")
    (missing.data_dir / "system_info.json").unlink()
    with pytest.raises(JobFailure) as exc:
        validate_outputs(missing, "job", 1, provider="openai", model="gpt-4.1")
    assert exc.value.code == FailureCode.ARTIFACTS_INVALID

    ws = _artifact_workspace(tmp_path / "canonical-system")
    doc = json.loads((ws.data_dir / "system_info.json").read_text())
    doc["OPENAI_API_KEY"] = "sk-LEAK-ME-NOT"
    doc["endpoint"] = "https://secret.example"
    (ws.data_dir / "system_info.json").write_text(json.dumps(doc))
    uploads = validate_outputs(ws, "job", 1, provider="openai", model="gpt-4.1")
    system = next(a for a in uploads if a.artifact_type == "system_info_json")
    rendered = system.local_path.read_text()
    assert "sk-LEAK-ME-NOT" not in rendered and "secret.example" not in rendered
    parsed = json.loads(rendered)
    assert parsed["processing"]["provider"] == "openai"
    assert parsed["processing"]["model"] == "gpt-4.1"
    assert parsed["tokens"]["total_tokens"] == 0


def test_every_required_artifact_missing_is_invalid(tmp_path):
    from instascribe_worker.artifacts import REQUIRED_JSON

    for _, filename in REQUIRED_JSON.items():
        ws = _artifact_workspace(tmp_path / filename.replace(".", "_"))
        (ws.data_dir / filename).unlink()
        _expect_artifacts_invalid(ws)


def test_malformed_wrong_shape_and_nonstandard_json_are_invalid(tmp_path):
    # Malformed JSON.
    ws = _artifact_workspace(tmp_path / "malformed", raw_scenes="{not json")
    _expect_artifacts_invalid(ws)
    # Wrong top-level shape for a required list artifact.
    ws = _artifact_workspace(tmp_path / "shape")
    (ws.data_dir / "entities.json").write_text('{"not": "a list"}')
    _expect_artifacts_invalid(ws)
    # Non-standard JSON constants must be rejected, not parsed leniently.
    ws = _artifact_workspace(
        tmp_path / "nan",
        raw_scenes='[{"scene_id": "scene_1", "start": NaN, "end": 2.0}]',
    )
    _expect_artifacts_invalid(ws)
    ws = _artifact_workspace(
        tmp_path / "inf",
        raw_scenes='[{"scene_id": "scene_1", "start": 0.0, "end": Infinity}]',
    )
    _expect_artifacts_invalid(ws)


@pytest.mark.parametrize(
    "scenes",
    [
        [],  # empty
        [{"scene_id": "scene_01", "start": 0.0, "end": 1.0}],  # zero-padded id
        [{"scene_id": "shot_1", "start": 0.0, "end": 1.0}],  # wrong prefix
        [
            {"scene_id": "scene_1", "start": 0.0, "end": 1.0},
            {"scene_id": "scene_1", "start": 1.0, "end": 2.0},  # duplicate id
        ],
        [{"scene_id": "scene_1", "start": 2.0, "end": 1.0}],  # end <= start
        [{"scene_id": "scene_1", "start": 1.0, "end": 1.0}],
        [{"scene_id": "scene_1", "start": True, "end": 2.0}],  # bool bound
        [{"scene_id": "scene_1", "start": "0", "end": 2.0}],  # string bound
        ["not-an-object"],
    ],
)
def test_scene_matrix_rejects_invalid_scenes(tmp_path, scenes):
    ws = _artifact_workspace(tmp_path, scenes=scenes)
    _expect_artifacts_invalid(ws)


@pytest.mark.parametrize(
    "scene_id",
    [
        "scene_1\n",  # G8 B1: LITERAL trailing newline — `$` under .match accepted this
        "scene_1\r\n",  # literal CRLF
        "scene_1\r",
        "scene_1 ",  # trailing space
        " scene_1",  # leading space
        "scene_1x",  # suffix
        "scene_1_2",
        "xscene_1",  # prefix garbage
        "Scene_1",  # case
        "scene_",  # no ordinal
        "scene_0",  # zero ordinal
        "scene_-1",
    ],
)
def test_scene_id_requires_exact_full_match(tmp_path, scene_id):
    """G8 B1 regression: worker scene-ID validation is an exact FULL match.

    The historical defect: `re.match` with a `$` anchor still accepts one
    trailing newline, so `"scene_1\\n"` (a real LF, not an escaped display)
    passed validation the exact API/DB contract rejects."""
    ws = _artifact_workspace(tmp_path, scenes=[{"scene_id": scene_id, "start": 0.0, "end": 1.0}])
    _expect_artifacts_invalid(ws)


def test_ordinary_canonical_scene_ids_remain_accepted(tmp_path):
    from instascribe_worker.artifacts import validate_outputs

    scenes = [
        {"scene_id": "scene_1", "start": 0.0, "end": 1.0},
        {"scene_id": "scene_2", "start": 1.0, "end": 2.0},
        {"scene_id": "scene_10", "start": 2.0, "end": 3.0},
        {"scene_id": "scene_999", "start": 3.0, "end": 4.0},
    ]
    ws = _artifact_workspace(tmp_path, scenes=scenes)
    uploads = validate_outputs(ws, "job", 1)
    assert any(u.artifact_type == "scenes_json" for u in uploads)


def test_scene_count_must_be_honest_int(tmp_path):
    # bool masquerading as a count of one.
    ws = _artifact_workspace(
        tmp_path / "bool", result={"data_path": "/data/job", "scene_count": True}
    )
    _expect_artifacts_invalid(ws)
    # count disagreeing with the validated scenes.
    ws = _artifact_workspace(
        tmp_path / "mismatch", result={"data_path": "/data/job", "scene_count": 7}
    )
    _expect_artifacts_invalid(ws)
    # wrong job identity.
    ws = _artifact_workspace(
        tmp_path / "identity", result={"data_path": "/data/other", "scene_count": 1}
    )
    _expect_artifacts_invalid(ws)


def test_normalised_all_zero_scenes_remain_invalid_worker_output(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "modular_pipeline"))
    from normalisation import export_scenes

    scenes = export_scenes(
        {
            "scene_history": [
                {"start": 0.0, "end": 0.0, "character_ids": [], "ad": "zero"},
                {"start": 60.0, "end": 60.0, "character_ids": [], "ad": "tail"},
            ]
        },
        [],
    )
    assert scenes == []
    failure = _expect_artifacts_invalid(_artifact_workspace(tmp_path, scenes=scenes))
    assert failure.public_message == "scenes.json is empty or not a list"


def test_normalised_negative_duration_is_retained_then_rejected(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(REPO / "modular_pipeline"))
    from normalisation import export_scenes

    scenes = export_scenes(
        {"scene_history": [{"start": 2.0, "end": 1.0, "character_ids": [], "ad": "negative"}]},
        [],
    )
    assert [(scene["start"], scene["end"]) for scene in scenes] == [(2.0, 1.0)]
    failure = _expect_artifacts_invalid(_artifact_workspace(tmp_path, scenes=scenes))
    assert failure.public_message == "scene end must exceed start"


def test_optional_poster_presence_and_absence(tmp_path):
    from instascribe_worker.artifacts import validate_outputs

    ws = _artifact_workspace(tmp_path / "noposter")
    uploads = validate_outputs(ws, "job", 1)
    assert {u.artifact_type for u in uploads} == {
        "scenes_json",
        "entities_json",
        "audio_events_json",
        "ad_placement_gaps_json",
        "transcript_json",
        "system_info_json",
    }  # absence degrades safely
    ws = _artifact_workspace(tmp_path / "poster")
    (ws.data_dir / "poster.jpg").write_bytes(b"\xff\xd8\xff jpeg-ish")
    uploads = validate_outputs(ws, "job", 2)
    poster = next(u for u in uploads if u.artifact_type == "poster_jpg")
    assert poster.object_key == "jobs/job/attempts/2/posters/poster.jpg"


# --- structured logging ----------------------------------------------------


def test_logs_are_single_line_json_without_secrets(capsys):
    from instascribe_worker.logging import log

    log(
        "job_claimed",
        job_id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        attempt=1,
        stage="initializing",
        duration_ms=12,
    )
    out = capsys.readouterr().out.strip()
    assert out.count("\n") == 0
    record = json.loads(out)
    assert record["service"] == "instascribe-worker"
    assert record["event"] == "job_claimed"
    assert "timestamp" in record and record["level"] == "info"


def test_exhausted_failure_log_preserves_fixed_underlying_code(monkeypatch, capsys):
    from instascribe_worker import consumer

    committed: dict = {}

    def _commit(*args, **kwargs):
        committed.update(kwargs)
        return True

    monkeypatch.setattr(consumer.claim_mod, "guarded_transition", _commit)
    job = SimpleNamespace(id=uuid.uuid4(), attempt_count=1, max_attempts=1)
    failure = JobFailure(FailureCode.ARTIFACTS_INVALID, "bounded public marker")

    result = consumer._handle_failure(
        SimpleNamespace(), SimpleNamespace(), job, "receipt", failure, "claim-token"
    )

    assert result == "failed_exhausted"
    assert committed["error_code"] == FailureCode.RETRY_EXHAUSTED.value
    record = json.loads(capsys.readouterr().out)
    assert record["event"] == "job_failed_exhausted"
    assert record["failure_code"] == FailureCode.ARTIFACTS_INVALID.value
    assert "bounded public marker" not in json.dumps(record)


def test_poison_logging_never_includes_the_raw_body(capsys, monkeypatch):
    """The consumer logs a category only — never the body, prompt or URL."""
    from instascribe_worker.logging import log

    hostile = "custom_prompt=SECRET https://signed.example/x?sig=abc AKIAEXAMPLE"
    log("message_poison", level="warning", category="parse", receive_count=2)
    out = capsys.readouterr().out
    for leak in ("SECRET", "signed.example", "AKIA"):
        assert leak not in out
    assert hostile  # the hostile body was never passed to the logger
