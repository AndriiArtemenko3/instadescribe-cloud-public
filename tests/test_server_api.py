"""Golden-parity harness for the Flask API.

These tests pin the behaviour of every endpoint against a temp data dir, so the
storage/export_service extraction can be verified to preserve it. The pipeline
subprocess and any OpenAI/ffmpeg paths are never exercised — only deterministic
logic is.
"""

import io
import json
import subprocess

import export_service
import pytest
import server
import storage


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """Redirect all on-disk storage to a temp tree and stub the pipeline launch."""
    app_dir = tmp_path / "App"
    data_dir = app_dir / "public" / "data"
    videos_dir = app_dir / "public" / "videos"
    jobs_dir = tmp_path / "jobs"
    for d in (data_dir, videos_dir, jobs_dir, app_dir / "dist"):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(storage, "APP_DIR", app_dir)
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "VIDEOS_DIR", videos_dir)
    monkeypatch.setattr(storage, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(storage, "DIST_DIR", app_dir / "dist")
    monkeypatch.setattr(server, "STUDY_LOGS_DIR", tmp_path / "study_logs")
    # Never launch the real pipeline.
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
    return tmp_path


@pytest.fixture
def client(tmp_env):
    server.app.config.update(TESTING=True)
    return server.app.test_client()


def _seed_job(job_id, status=None, settings=None, meta=None):
    jdir = storage.JOBS_DIR / job_id
    jdir.mkdir(parents=True, exist_ok=True)
    (jdir / "status.json").write_text(json.dumps(status or {"status": "ready", "progress": 100}))
    if settings is not None:
        (jdir / "settings.json").write_text(json.dumps(settings))
    if meta is not None:
        (jdir / "meta.json").write_text(json.dumps(meta))
    return jdir


def _seed_data(job_id, scenes, entities=None):
    ddir = storage.DATA_DIR / job_id
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / "scenes.json").write_text(json.dumps(scenes))
    if entities is not None:
        (ddir / "entities.json").write_text(json.dumps(entities))
    return ddir


# ── create_job ────────────────────────────────────────────────────────────────


def test_create_job_requires_video(client):
    assert client.post("/api/jobs").status_code == 400


def test_create_job_rejects_bad_settings(client):
    r = client.post(
        "/api/jobs",
        data={"video": (io.BytesIO(b"x"), "v.mp4"), "settings": "{not json"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400


def test_create_job_happy_path(client):
    r = client.post(
        "/api/jobs",
        data={
            "video": (io.BytesIO(b"fake"), "v.mp4"),
            "settings": json.dumps(
                {"name": "Test", "settings": {"model": "gpt-4.1"}, "durationSecs": 12}
            ),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 202
    body = r.get_json()
    assert body["jobId"] == body["projectId"]
    jid = body["jobId"]
    status = json.loads((storage.JOBS_DIR / jid / "status.json").read_text())
    assert status["status"] == "queued"
    settings = json.loads((storage.JOBS_DIR / jid / "settings.json").read_text())
    assert settings["model"] == "gpt-4.1"
    assert settings["project_name"] == "Test"


# ── get / list / delete / patch meta ────────────────────────────────────────────


def test_get_job_not_found(client):
    assert client.get("/api/jobs/missing").get_json()["status"] == "not_found"


def test_list_and_batch(client):
    _seed_job("job-a", status={"status": "ready", "progress": 100}, settings={"project_name": "A"})
    _seed_job("job-b", status={"status": "queued", "progress": 0})
    allj = client.get("/api/jobs").get_json()
    assert set(allj) == {"job-a", "job-b"}
    one = client.get("/api/jobs?ids=job-a").get_json()
    assert set(one) == {"job-a"}
    assert one["job-a"]["project_name"] == "A"


def test_delete_job(client):
    assert client.delete("/api/jobs/bad id").status_code == 400  # space → invalid
    assert client.delete("/api/jobs/ghost").status_code == 204  # idempotent
    _seed_job("job-d")
    assert client.delete("/api/jobs/job-d").status_code == 204
    assert not (storage.JOBS_DIR / "job-d").exists()


def test_patch_job_meta(client):
    assert client.patch("/api/jobs/bad id").status_code == 400
    assert client.patch("/api/jobs/ghost", json={"name": "x"}).status_code == 404
    _seed_job("job-m")
    r = client.patch("/api/jobs/job-m", json={"name": "  Renamed  ", "starred": True})
    meta = r.get_json()
    assert meta["name"] == "Renamed" and meta["starred"] is True


# ── scene overrides (the lock-protected read-modify-write) ──────────────────────


def test_patch_scene_and_get_overrides(client):
    _seed_job("job-s")
    r = client.patch(
        "/api/jobs/job-s/scenes/scene_1",
        json={"ad": "new line", "active": False, "locked": True, "voice": "nova"},
    )
    ov = r.get_json()["override"]
    assert ov == {"ad": "new line", "active": False, "locked": True, "voice": "nova"}
    # An invalid voice is silently ignored, not stored.
    client.patch("/api/jobs/job-s/scenes/scene_1", json={"voice": "bogus"})
    stored = client.get("/api/jobs/job-s/overrides").get_json()
    assert stored["scene_1"]["voice"] == "nova"


# ── entity rename ───────────────────────────────────────────────────────────────


def test_patch_entity_rename_rerenders_scenes(client):
    _seed_job("job-e")
    _seed_data(
        "job-e",
        scenes=[
            {
                "scene_id": "scene_1",
                "caption_template": "{char_1_first} runs.",
                "caption": "old",
                "locked": False,
            }
        ],
        entities=[
            {"id": "char_1", "name": "a man", "first_mention_label": "a man", "pronoun": "he"}
        ],
    )
    r = client.patch("/api/jobs/job-e/entities/char_1", json={"name": "Indiana"})
    assert r.status_code == 200
    scenes = json.loads((storage.DATA_DIR / "job-e" / "scenes.json").read_text())
    assert scenes[0]["caption"] == "Indiana runs."

    assert client.patch("/api/jobs/job-e/entities/char_9", json={"name": "X"}).status_code == 404
    assert client.patch("/api/jobs/job-x/entities/char_1", json={"name": "X"}).status_code == 404


# ── merged scenes (override precedence + zero-duration drop) ─────────────────────


def test_merged_scenes_applies_overrides_and_drops_zero_duration(tmp_env):
    _seed_job("job-merge")
    _seed_data(
        "job-merge",
        scenes=[
            {"scene_id": "scene_1", "start": 0.0, "end": 5.0, "caption": "first"},
            {"scene_id": "scene_2", "start": 5.0, "end": 5.0, "caption": "zero-length"},
        ],
    )
    storage.write_overrides(
        "job-merge", {"scene_1": {"ad": "edited", "active": False, "voice": "nova"}}
    )
    merged = export_service.merged_scenes("job-merge")
    assert len(merged) == 1  # zero-duration scene dropped
    assert merged[0]["text"] == "edited"  # override "ad" wins over caption
    assert merged[0]["active"] is False  # override active wins
    assert merged[0]["voice"] == "nova"


# ── export validation + start ───────────────────────────────────────────────────


def test_export_validation(client, monkeypatch):
    # Stub the background render thread so start_export's contract is tested in
    # isolation (no ffmpeg/TTS, no teardown race on the temp dir).
    class _NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            pass

    monkeypatch.setattr(server.threading, "Thread", _NoThread)

    assert client.post("/api/jobs/bad id/export").status_code == 400
    assert client.post("/api/jobs/ghost/export").status_code == 404
    _seed_job("job-ex")  # no scenes.json yet
    assert client.post("/api/jobs/job-ex/export", json={"format": "srt"}).status_code == 409
    _seed_data("job-ex", scenes=[{"scene_id": "scene_1", "start": 0, "end": 2, "caption": "x"}])
    assert client.post("/api/jobs/job-ex/export", json={"format": "weird"}).status_code == 400
    r = client.post("/api/jobs/job-ex/export", json={"format": "srt"})
    assert r.status_code == 202 and "exportId" in r.get_json()


def test_export_status_and_download_not_ready(client):
    _seed_job("job-ex2")
    assert client.get("/api/jobs/job-ex2/export/nope").status_code == 404
    assert client.get("/api/jobs/job-ex2/export/nope/download").status_code == 404


# ── study mode ──────────────────────────────────────────────────────────────────


def test_study_session_provision_is_idempotent(client, monkeypatch):
    monkeypatch.setattr(server, "STUDY_SOURCE_JOB", "studysrc")
    _seed_data("studysrc", scenes=[{"scene_id": "scene_1", "start": 0, "end": 3, "caption": "c"}])
    r1 = client.post("/api/study/session", json={"sessionId": "sess-1"})
    assert r1.status_code == 200
    body = r1.get_json()
    assert body["projectId"] == "sess-1" and body["dataPath"] == "/data/sess-1"
    assert (storage.DATA_DIR / "sess-1" / "scenes.json").exists()
    # Scenes are seeded inactive for the study.
    ov = json.loads(storage.overrides_path("sess-1").read_text())
    assert ov["scene_1"] == {"active": False}
    # Returning session reuses its copy without error.
    assert client.post("/api/study/session", json={"sessionId": "sess-1"}).status_code == 200


def test_study_session_requires_valid_id(client):
    assert client.post("/api/study/session", json={}).status_code == 400


def test_study_log_appends(client):
    assert client.post("/api/log", json={}).status_code == 400
    assert (
        client.post("/api/log", json={"sessionId": "sess-1", "event": "edit", "ts": 1}).status_code
        == 204
    )
    line = json.loads((server.STUDY_LOGS_DIR / "sess-1.jsonl").read_text().strip())
    assert line["event"] == "edit"


def test_study_config_defaults(client):
    cfg = client.get("/api/study/config").get_json()
    assert cfg["questionnaireParam"] == "session"


# ── static serving ──────────────────────────────────────────────────────────────


def test_serve_data_file(client):
    (storage.DATA_DIR / "demo").mkdir(parents=True, exist_ok=True)
    (storage.DATA_DIR / "demo" / "scenes.json").write_text('{"ok": true}')
    r = client.get("/data/demo/scenes.json")
    assert r.status_code == 200 and r.get_json() == {"ok": True}


def test_serve_index_without_build(client):
    r = client.get("/")
    assert r.status_code == 200 and "backend running" in r.get_json()["status"]


def test_api_unknown_route_is_404(client):
    assert client.get("/api/does-not-exist").status_code == 404


# ── evaluation endpoint ─────────────────────────────────────────────────────────


def test_evaluation_endpoint(client):
    assert client.get("/api/jobs/bad id/evaluation").status_code == 400
    assert client.get("/api/jobs/ghost/evaluation").status_code == 404
    _seed_job("job-ev")
    ddir = _seed_data(
        "job-ev",
        scenes=[
            {
                "scene_id": "scene_1",
                "start": 0,
                "end": 5,
                "caption": "a man waves",
                "character_ids": [],
            }
        ],
    )
    (ddir / "audio_events.json").write_text(json.dumps([]))
    (ddir / "entities.json").write_text(json.dumps([]))
    body = client.get("/api/jobs/job-ev/evaluation").get_json()
    assert body["active_count"] == 1
    assert 0.0 <= body["overall"] <= 1.0
    assert set(body["dimensions"]) == {
        "timing",
        "dialogue_safety",
        "coverage",
        "character_consistency",
        "grounding",
    }
