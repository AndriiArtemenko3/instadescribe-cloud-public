"""Worker entrypoint: deterministic --once mode for tests/smoke, and a
bounded-shutdown continuous mode for Compose/ECS.

G5.1 B1/B3 hardening: SIGTERM/SIGINT terminate and reap the whole owned
process TREE (not just the direct child); invalid configuration exits nonzero
with a category-only event (no raw Pydantic traceback, no input values);
infrastructure failures in the receive/claim path surface as the sanitized
`infra_error` outcome — continuous mode applies bounded backoff instead of a
hot crash/restart loop, and --once exits nonzero after one such failure.
"""

import argparse
import signal
import sys
import threading

from pydantic import ValidationError

from instascribe_worker import executor
from instascribe_worker.config import get_worker_settings
from instascribe_worker.consumer import run_once
from instascribe_worker.logging import log

_stop = threading.Event()

BACKOFF_INITIAL_SECS = 1.0
BACKOFF_MAX_SECS = 30.0


def _handle_sigterm(signum, frame) -> None:
    _stop.set()
    try:
        grace = get_worker_settings().grace_secs
    except Exception:
        grace = 10
    executor.terminate_current(grace)
    log("worker_shutdown_requested", level="warning")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="instascribe-worker")
    parser.add_argument(
        "--once", action="store_true", help="consume at most one message, then exit"
    )
    args = parser.parse_args(argv)
    try:
        settings = get_worker_settings()  # fails fast on invalid configuration
    except ValidationError as exc:
        # Category + field COUNT only — hide_input_in_errors already strips
        # values, and we never echo the error body at all.
        log(
            "worker_config_invalid",
            level="error",
            category="config",
            error_count=exc.error_count(),
        )
        return 1
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)
    log(
        "worker_started",
        worker_label=settings.worker_id,
        once=args.once,
        long_poll_secs=settings.long_poll_secs,
    )
    if args.once:
        outcome = run_once(settings)
        log("worker_once_complete", outcome=outcome)
        return 1 if outcome == "infra_error" else 0
    backoff = BACKOFF_INITIAL_SECS
    while not _stop.is_set():
        outcome = run_once(settings)
        if outcome != "empty":
            log("worker_cycle", outcome=outcome)
        if outcome == "infra_error":
            # Bounded backoff, interruptible by shutdown — never a hot loop.
            _stop.wait(backoff)
            backoff = min(backoff * 2, BACKOFF_MAX_SECS)
        else:
            backoff = BACKOFF_INITIAL_SECS
    log("worker_stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
