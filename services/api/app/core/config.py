"""Typed application configuration.

`DATABASE_URL` and every secret-adjacent value are supplied by the environment
(Compose locally, the task definition + Secrets Manager in AWS). The DSN and
the portfolio-token digest must never be logged or echoed into responses —
nothing in this module or its consumers prints them. Only clearly documented
local/test placeholder material may appear in the repository.
"""

from functools import lru_cache
from typing import ClassVar

from instascribe_contracts.provider import (
    OPENAI_G12_MAX_DURATION_SECS,
    PROVIDER_ALLOWLIST,
    PROVIDER_MAX_ATTEMPTS,
    ProviderName,
)
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # validate_default: misconfigured explicit values fail fast at load
    # instead of surfacing as runtime surprises.
    model_config = SettingsConfigDict(extra="ignore", validate_default=True)

    # Absent DATABASE_URL keeps liveness working and turns readiness 503
    # ("configuration") instead of crashing the process at import.
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    # FastAPI docs/OpenAPI routes: enabled locally, switched off for the
    # public portfolio environment before G9 (G1 review correction #4).
    enable_docs: bool = Field(default=True, validation_alias="INSTASCRIBE_ENABLE_DOCS")

    # --- G3: portfolio token (SHA-256 hex digest of the token, never the token) ---
    portfolio_token_sha256: str | None = Field(
        default=None, validation_alias="PORTFOLIO_TOKEN_SHA256"
    )

    # --- G3: S3/media configuration ---
    media_bucket: str = Field(
        default="instascribe-media", validation_alias="INSTASCRIBE_MEDIA_BUCKET"
    )
    aws_region: str = Field(default="eu-west-2", validation_alias="AWS_DEFAULT_REGION")
    # Split endpoint views: SDK calls vs browser-visible presigned URLs.
    # None means real AWS endpoints (deployment).
    s3_endpoint_internal: str | None = Field(
        default=None, validation_alias="INSTASCRIBE_S3_ENDPOINT_INTERNAL"
    )
    s3_endpoint_public: str | None = Field(
        default=None, validation_alias="INSTASCRIBE_S3_ENDPOINT_PUBLIC"
    )
    s3_force_path_style: bool = Field(
        default=False, validation_alias="INSTASCRIBE_S3_FORCE_PATH_STYLE"
    )
    # Conservative numeric bounds (not truthiness): a mistyped expiry or limit
    # fails configuration load rather than producing surprising policies.
    presign_expiry_secs: int = Field(
        default=900, ge=60, le=3600, validation_alias="INSTASCRIBE_PRESIGN_EXPIRY_SECS"
    )
    # G6: manifest download URLs are deliberately shorter-lived than upload
    # POSTs — one manifest request signs every reference against one common
    # expiry instant; URLs are never persisted or logged.
    download_presign_expiry_secs: int = Field(
        default=300, ge=60, le=900, validation_alias="INSTASCRIBE_DOWNLOAD_PRESIGN_EXPIRY_SECS"
    )

    # --- G4: SQS (container-internal endpoint only — never the browser view) ---
    sqs_endpoint_internal: str | None = Field(
        default=None, validation_alias="INSTASCRIBE_SQS_ENDPOINT_INTERNAL"
    )
    work_queue_name: str = Field(
        default="instascribe-work",
        min_length=1,
        max_length=80,
        validation_alias="INSTASCRIBE_WORK_QUEUE",
    )
    work_queue_url: str | None = Field(default=None, validation_alias="INSTASCRIBE_WORK_QUEUE_URL")

    @field_validator("work_queue_url")
    @classmethod
    def _queue_url_shape(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")) or len(v) > 512:
            raise ValueError("work queue URL must be a bounded http(s) URL")
        return v

    # --- G3: portfolio limits and spend bounds (server-authoritative) ---
    max_upload_bytes: int = Field(
        default=250 * 1024 * 1024,
        ge=1,
        le=1024 * 1024 * 1024,
        validation_alias="INSTASCRIBE_MAX_UPLOAD_BYTES",
    )
    max_duration_secs: int = Field(
        default=300, ge=1, le=3600, validation_alias="INSTASCRIBE_MAX_DURATION_SECS"
    )
    max_attempts: int = Field(default=3, ge=1, le=3, validation_alias="INSTASCRIBE_MAX_ATTEMPTS")
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173"], validation_alias="INSTASCRIBE_ALLOWED_ORIGINS"
    )
    # The client never selects a provider or pipeline revision. This is a
    # code-bounded deployment setting; no environment variable can widen the
    # exact fake/openai set.
    provider: ProviderName = Field(default="fake", validation_alias="INSTASCRIBE_PROVIDER")
    provider_allowlist: ClassVar[tuple[ProviderName, ...]] = PROVIDER_ALLOWLIST
    model_allowlist: tuple[str, ...] = ("gpt-4.1",)
    fps_allowlist: tuple[float, ...] = (0.5, 1.0)
    frame_quality_allowlist: tuple[str, ...] = ("low",)
    chunk_size_allowlist: tuple[int, ...] = (60, 120)
    preset_style_allowlist: tuple[str, ...] = (
        "documentary",
        "cinematic",
        "news",
        "sports",
        "education",
    )
    allowed_content_types: tuple[str, ...] = ("video/mp4", "video/quicktime", "video/webm")
    allowed_extensions: tuple[str, ...] = (".mp4", ".mov", ".webm")

    # Immutable server-supplied provenance ('dev' locally; the immutable
    # code/image revision in deployment). Clients may never choose it.
    pipeline_revision: str | None = Field(
        default=None, validation_alias="INSTASCRIBE_PIPELINE_REVISION"
    )

    @field_validator("pipeline_revision")
    @classmethod
    def _revision_trimmed_and_bounded(cls, v: str | None) -> str | None:
        # None stays allowed (readiness reports 'configuration'); an explicit
        # value must be non-empty after trimming and fit the 120-char column.
        if v is None:
            return None
        v = v.strip()
        if not 1 <= len(v) <= 120:
            raise ValueError("pipeline revision must be 1-120 characters after trimming")
        return v

    @model_validator(mode="after")
    def _g12_provider_limits(self) -> "Settings":
        # Real-provider G12 is a bounded smoke, not an unbounded public SaaS
        # workload. Fake remains compatible with the existing five-minute
        # local/cloud evaluation path.
        if self.provider == "openai" and self.max_duration_secs > OPENAI_G12_MAX_DURATION_SECS:
            raise ValueError("OpenAI G12 duration limit must not exceed 120 seconds")
        if self.max_attempts != PROVIDER_MAX_ATTEMPTS[self.provider]:
            raise ValueError("configured attempt bound does not match provider policy")
        return self

    def token_digest_valid(self) -> bool:
        d = self.portfolio_token_sha256
        return bool(d) and len(d) == 64 and all(c in "0123456789abcdefABCDEF" for c in d)


@lru_cache
def get_settings() -> Settings:
    return Settings()
