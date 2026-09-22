"""Typed worker configuration — independent of the API's settings module.

The worker never imports FastAPI startup or API token/CORS settings. Missing
or invalid required configuration fails fast WITHOUT printing secret values
(`hide_input_in_errors` strips inputs from validation errors, and the
entrypoint additionally reduces any validation failure to a category event).
"""

from functools import lru_cache
from typing import ClassVar

from instascribe_contracts.provider import (
    OPENAI_G12_MAX_DURATION_SECS,
    PROVIDER_ALLOWLIST,
    PROVIDER_MAX_ATTEMPTS,
    ProviderName,
)
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", validate_default=True, hide_input_in_errors=True
    )

    database_url: str = Field(validation_alias="DATABASE_URL", min_length=1)
    # Deployment-level provider selection. The queue carries no provider
    # input; jobs are stamped by the API and must exactly match this worker.
    provider: ProviderName = Field(default="fake", validation_alias="INSTASCRIBE_PROVIDER")
    provider_allowlist: ClassVar[tuple[ProviderName, ...]] = PROVIDER_ALLOWLIST
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    aws_region: str = Field(default="eu-west-2", validation_alias="AWS_DEFAULT_REGION")
    s3_endpoint_internal: str | None = Field(
        default=None, validation_alias="INSTASCRIBE_S3_ENDPOINT_INTERNAL"
    )
    sqs_endpoint_internal: str | None = Field(
        default=None, validation_alias="INSTASCRIBE_SQS_ENDPOINT_INTERNAL"
    )
    media_bucket: str = Field(
        default="instascribe-media", min_length=1, validation_alias="INSTASCRIBE_MEDIA_BUCKET"
    )
    work_queue_name: str = Field(
        default="instascribe-work",
        min_length=1,
        max_length=80,
        validation_alias="INSTASCRIBE_WORK_QUEUE",
    )
    work_queue_url: str | None = Field(default=None, validation_alias="INSTASCRIBE_WORK_QUEUE_URL")

    worker_id: str = Field(
        default="worker-local",
        min_length=1,
        max_length=120,
        validation_alias="INSTASCRIBE_WORKER_ID",
    )
    long_poll_secs: int = Field(
        default=10, ge=0, le=20, validation_alias="INSTASCRIBE_LONG_POLL_SECS"
    )
    subprocess_timeout_secs: int = Field(
        default=1500, ge=30, le=1700, validation_alias="INSTASCRIBE_SUBPROCESS_TIMEOUT_SECS"
    )
    grace_secs: int = Field(default=10, ge=1, le=60, validation_alias="INSTASCRIBE_GRACE_SECS")
    max_duration_secs: int = Field(
        default=300, ge=1, le=3600, validation_alias="INSTASCRIBE_MAX_DURATION_SECS"
    )
    max_attempts: int = Field(default=3, ge=1, le=3, validation_alias="INSTASCRIBE_MAX_ATTEMPTS")
    # Bounded G12 cost controls. They are passed to the subprocess only in
    # OpenAI mode; fake children retain the pipeline's historical defaults.
    max_provider_calls: int = Field(
        default=6, ge=1, le=6, validation_alias="INSTASCRIBE_MAX_PROVIDER_CALLS"
    )
    max_provider_output_tokens: int = Field(
        default=8000,
        ge=1,
        le=8000,
        validation_alias="INSTASCRIBE_MAX_PROVIDER_OUTPUT_TOKENS",
    )
    workspace_root: str | None = Field(default=None, validation_alias="INSTASCRIBE_WORKSPACE_ROOT")
    retry_visibility_delay_secs: int = Field(
        default=30, ge=0, le=900, validation_alias="INSTASCRIBE_RETRY_VISIBILITY_DELAY_SECS"
    )
    # Where the immutable pipeline source lives (copied per attempt).
    pipeline_source: str = Field(
        default="/app/modular_pipeline", validation_alias="INSTASCRIBE_PIPELINE_SOURCE"
    )
    # REQUIRED provenance binding (G5.1 B4): 'dev' locally, the immutable
    # image/commit revision later. A claimed job whose persisted revision
    # differs fails deterministically as pipeline_revision_mismatch — it is
    # never silently processed under false provenance. Not a secret; not
    # client-controlled (the API stamps it server-side at creation).
    # Same semantics as the API/DB contract (G8 B2): trimmed, non-empty,
    # at most 120 characters — the sa.String(120) column bound.
    pipeline_revision: str = Field(validation_alias="INSTASCRIBE_PIPELINE_REVISION")

    @field_validator("pipeline_revision")
    @classmethod
    def _revision_trimmed_and_bounded(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 120:
            raise ValueError("pipeline revision must be 1-120 characters after trimming")
        return v

    @field_validator("work_queue_url")
    @classmethod
    def _queue_url_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")) or len(v) > 512:
            raise ValueError("work queue URL must be a bounded http(s) URL")
        return v

    @model_validator(mode="after")
    def _g12_provider_requirements(self) -> "WorkerSettings":
        if self.provider == "openai":
            key = self.openai_api_key.get_secret_value() if self.openai_api_key else ""
            if not key or key != key.strip():
                # The validation body is never logged; main emits a category
                # and count only. Do not include key material in this message.
                raise ValueError("OpenAI worker credential is missing or invalid")
            if self.max_duration_secs > OPENAI_G12_MAX_DURATION_SECS:
                raise ValueError("OpenAI G12 duration limit must not exceed 120 seconds")
        if self.max_attempts != PROVIDER_MAX_ATTEMPTS[self.provider]:
            raise ValueError("configured attempt bound does not match provider policy")
        return self


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


def reset_worker_settings() -> None:
    get_worker_settings.cache_clear()
