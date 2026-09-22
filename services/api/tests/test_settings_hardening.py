"""Part A3: settings default-validation, numeric bounds, control characters."""

import pytest
from app.core.config import Settings, get_settings
from app.schemas.jobs import CreateJobRequest, UploadSettingsIn
from pydantic import ValidationError


def test_invalid_configured_default_fails_even_when_request_omits_the_field(monkeypatch):
    # Shrink the server allowlists so the schema defaults become invalid; a
    # request that omits settings entirely must now fail (validate_default).
    settings = get_settings()
    monkeypatch.setattr(settings, "model_allowlist", ("some-other-model",))
    with pytest.raises(ValidationError):
        UploadSettingsIn()  # default model now violates the configured allowlist


def test_settings_numeric_bounds_are_enforced(monkeypatch):
    monkeypatch.setenv("INSTASCRIBE_PRESIGN_EXPIRY_SECS", "5")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("INSTASCRIBE_PRESIGN_EXPIRY_SECS", "900")
    monkeypatch.setenv("INSTASCRIBE_MAX_UPLOAD_BYTES", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_api_provider_policy_and_g12_duration_are_exact(monkeypatch):
    monkeypatch.setenv("INSTASCRIBE_PROVIDER", "unsupported")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("INSTASCRIBE_PROVIDER", "openai")
    monkeypatch.setenv("INSTASCRIBE_MAX_DURATION_SECS", "121")
    monkeypatch.setenv("INSTASCRIBE_MAX_ATTEMPTS", "1")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("INSTASCRIBE_MAX_DURATION_SECS", "120")
    assert Settings().provider == "openai"
    monkeypatch.setenv("INSTASCRIBE_MAX_ATTEMPTS", "3")
    with pytest.raises(ValidationError):
        Settings()


def test_pipeline_revision_trim_and_bound(monkeypatch):
    monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", "   ")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", "x" * 121)
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("INSTASCRIBE_PIPELINE_REVISION", "  rev-1  ")
    assert Settings().pipeline_revision == "rev-1"


def _payload(**overrides):
    base = {
        "name": "ok",
        "durationSecs": 10.0,
        "fileName": "a.mp4",
        "contentType": "video/mp4",
        "fileSizeBytes": 100,
    }
    base.update(overrides)
    return base


def test_nul_and_control_characters_are_validation_errors_not_500s():
    with pytest.raises(ValidationError):
        CreateJobRequest.model_validate(_payload(name="bad\x00name"))
    with pytest.raises(ValidationError):
        CreateJobRequest.model_validate(_payload(name="bad\x1bname"))
    with pytest.raises(ValidationError):
        CreateJobRequest.model_validate(_payload(settings={"customPrompt": "bad\x00prompt"}))
    # Prompts may keep normal whitespace controls.
    req = CreateJobRequest.model_validate(_payload(settings={"customPrompt": "line1\nline2\t."}))
    assert "\n" in req.settings.custom_prompt
