"""Exact source download (B6, hardened by G5.1 C1/C2): the persisted
bucket/key pinned to the EXACT persisted VersionId — the reusable presigned
POST can write a newer object at the same key, so "latest" is never the
processed source. A missing pinned version, 412, or any identity drift is a
deterministic non-retryable failure.

C2: the response StreamingBody is closed in `finally` on every path
(mismatch, overflow, stream exception). When a trustworthy checksum was
persisted at verification time, checksum response mode is requested and the
returned value must be PRESENT and equal — absence is an identity failure,
never silently skipped.
"""

import hashlib
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from instascribe_worker.failures import FailureCode, JobFailure

_CHUNK = 1024 * 1024


def download_source(s3, bucket: str, job, dest: Path) -> str:
    """Download the verified source to `dest`; returns the local SHA-256."""
    if not job.source_version_id:
        raise JobFailure(
            FailureCode.SOURCE_IDENTITY_MISMATCH,
            "job has no pinned source version; cannot prove source identity",
        )
    kwargs = {
        "Bucket": bucket,
        "Key": job.input_object_key,
        "VersionId": job.source_version_id,
    }
    if job.source_checksum_sha256:
        kwargs["ChecksumMode"] = "ENABLED"
    try:
        response = s3.get_object(**kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code == "PreconditionFailed" or status == 412 or code == "NoSuchVersion":
            raise JobFailure(
                FailureCode.SOURCE_IDENTITY_MISMATCH,
                "source object no longer matches its verified identity",
            ) from None
        raise JobFailure(FailureCode.SOURCE_DOWNLOAD_FAILED, "source download failed") from None
    except BotoCoreError:
        raise JobFailure(
            FailureCode.SOURCE_DOWNLOAD_FAILED, "source download transport failure"
        ) from None

    body = response["Body"]
    try:
        etag = (response.get("ETag") or "").strip('"')
        if etag != job.source_etag:
            raise JobFailure(
                FailureCode.SOURCE_IDENTITY_MISMATCH, "source ETag changed after verification"
            )
        if response.get("VersionId") != job.source_version_id:
            raise JobFailure(
                FailureCode.SOURCE_IDENTITY_MISMATCH, "source version changed after verification"
            )
        if job.source_checksum_sha256:
            remote_checksum = response.get("ChecksumSHA256")
            if not remote_checksum:
                raise JobFailure(
                    FailureCode.SOURCE_IDENTITY_MISMATCH,
                    "persisted checksum evidence is missing from the source response",
                )
            if remote_checksum != job.source_checksum_sha256:
                raise JobFailure(
                    FailureCode.SOURCE_IDENTITY_MISMATCH,
                    "source checksum changed after verification",
                )

        expected = job.input_size_bytes
        digest = hashlib.sha256()
        written = 0
        try:
            with open(dest, "wb") as out:
                for chunk in body.iter_chunks(_CHUNK):
                    written += len(chunk)
                    if written > expected:  # hard byte bound while streaming
                        raise JobFailure(
                            FailureCode.SOURCE_IDENTITY_MISMATCH,
                            "source larger than its verified size",
                        )
                    digest.update(chunk)
                    out.write(chunk)
        except JobFailure:
            raise
        except Exception:
            raise JobFailure(
                FailureCode.SOURCE_DOWNLOAD_FAILED, "source stream interrupted"
            ) from None
        if written != expected:
            raise JobFailure(
                FailureCode.SOURCE_IDENTITY_MISMATCH, "source smaller than its verified size"
            )
        return digest.hexdigest()
    finally:
        try:
            body.close()
        except Exception:
            pass
