# G0 container-feasibility evidence

**Date:** 2026-08-06 · **Gate:** Phase 1 G0 (G0a runtime/control proof + G0b pipeline-probe worker image)
**Scope:** feasibility evidence only — no API/SQS/PostgreSQL/LocalStack/Terraform/AWS integration. G5 builds its worker modules on this image foundation.

## G0a — runtime, builder, control-image, and platform proof

| Item | Evidence |
|---|---|
| Docker | client/server 29.6.2, Docker Desktop 4.85.0, engine `linux/arm64` (Apple Silicon host) |
| Builder | buildx v0.35.0-desktop.2, BuildKit v0.31.2; builders `default` + `desktop-linux`, both listing `linux/amd64` among platforms |
| Host | 12 CPU, 24 GiB RAM, 282 GiB free disk (Darwin 25.4.0) |
| Target declaration | **`linux/amd64`** for the worker image (ECS-compatible; ARM64 only after the torch/faster-whisper stack is verified on Fargate ARM) — every build below passed `--platform linux/amd64` |
| Control build | existing root `Dockerfile` built clean as `linux/amd64`: **64 s wall**, image `instascribe-control:g0`, 249 MB unpacked, 1,331 BuildKit log lines, zero errors |
| Context hygiene | `.dockerignore` excludes `.env`/`**/.env`, `modular_pipeline/jobs`, `study_logs`, `node_modules`, and allowlists only the Sintel fixture media; image contents limited to `COPY`ed paths (`modular_pipeline/`, `App/dist`, `App/public`); no credentials, runtime job data, or unrelated assets in either image |

## G0b — worker image design

Files (all new, owned by G0): `services/worker/Dockerfile`, `services/worker/requirements.in`, compiled `services/worker/requirements.txt`, `services/worker/app/g0_smoke.py`.

- **Base:** `python:3.12-slim` (Python 3.12.13 in-image), ffmpeg + ffprobe via apt (ffmpeg 7.x/deb13).
- **Dependencies:** compiled and fully pinned by `uv pip compile --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --index-strategy unsafe-best-match --emit-index-url` — 44 packages, **CPU-only torch** (`torch==2.13.0+cpu`, `torchaudio==2.11.0+cpu` from the PyTorch CPU index; **zero `nvidia-*` packages**), `faster-whisper==1.2.1`-line stack, index URLs embedded so plain `pip install -r` reproduces. Flask/flask-cors are deliberately absent (server-only; nothing in the `run_job.py` import chain touches them).
- **Weights baked:** faster-whisper **`medium`** downloaded at build into `/home/worker/.cache/instascribe` (the exact `download_root` the pipeline uses, `audio_whisperx_pipeline.py:45–46`); `HF_HUB_OFFLINE=1` set after baking, so runtime lookups resolve from the baked cache only. **No runtime model download remains** (silero-vad ships its weights inside the pip package). **Reproducibility caveat:** the build follows the moving `medium` alias (`Systran/faster-whisper-medium@main`); at G0 build time it resolved to snapshot **`08e178d48790749d25932bbc082711ddcfdfbc4f`**. The **production** worker target must pin both this model revision and the base-image digest **before G9** so cloud builds are byte-reproducible.
- **Non-root:** runtime user `worker` (uid 10001); writable bounded paths: `/app/modular_pipeline/jobs`, `/app/App/public/{data,videos}`, `/home/worker/.cache`, `/tmp`.
- **Pipeline untouched:** `modular_pipeline/` copied as-is; the probe invokes the existing `run_job.py <job_id> <settings.json>` subprocess contract in a synthesized job workspace (`g0_smoke.py` mirrors the server's seeding: job dir + `video.mp4` + `settings.json` + queued `status.json`).
- **Fixture:** the committed Sintel clip (CC BY 3.0), 120.0 s, copied into the image as the probe input.

## Build and image measurements

| Metric | Value |
|---|---|
| Worker image build (cold cache, incl. weight download + emulated pip) | **233 s wall** |
| Unpacked image size | **2.04 GB** (`docker image inspect`: 2,039,194,600 B) |
| Compressed transfer estimate (`docker save \| gzip -1`) | **2.03 GB** (weights dominate and are already compressed) |
| Architecture (image inspect) | `linux/amd64` |
| Verification rebuild from clean context (`--no-cache`, post-final-edits) | **259 s wall**, identical design; smoke re-run passed |

## Acceptance runs (fake provider, audio extraction ON, `--network none`)

Both runs used `INSTASCRIBE_BACKEND=fake` with networking disabled — proof that no external or paid-provider call is required end-to-end (the smoke script additionally refuses any non-`fake` backend).

**Run 1 — 4 GB memory cap (planned Fargate sizing): FAILED, and the gate caught it.**
The nested faster-whisper transcription subprocess was SIGKILLed (`Transcription subprocess failed (exit -9)`) with cgroup `memory.peak` pinned at exactly 4 GiB — an OOM at the cap. Whisper-`medium` float32 on CPU does not fit a 4 GB task alongside torch/VAD. `run_job.py`'s in-`main()` handler classified it correctly (`status: failed`, traceback preserved, exit 1). **Consequence: the §6 worker task sizing of ~1 vCPU/4 GB is disproven; v0.1 sizing moves to ≥8 GB (Fargate 1–2 vCPU × 8 GB is valid) — see risk R2 update.**

**Run 2 — 8 GB memory cap: PASS** (container exit 0, `OOMKilled=false`)

| Metric | Value |
|---|---|
| Fixture job exit code | 0 |
| Processing duration (fixture job, under amd64 emulation) | **90.3 s** for the 120 s clip — native Fargate amd64 will differ; re-measured at G11 |
| Container memory peak (cgroup `memory.peak`) | **6.57 GiB** |
| Peak CPU (10 s host samples, run 1) | ~117–132 % of one core (multi-threaded phases; run-2 sampler lost to a shell quirk, run-1 profile retained) |
| End-state workspace | jobs dir 23.4 MB (frames + video + work), data dir 82 KB, public video copy 8.9 MB, /tmp 2.7 KB — comfortably bounded |
| Artifact validation | **all required checks true**: non-empty `scenes.json`, valid `entities.json`, valid + non-empty `audio_events.json` (real VAD/ASR output), valid `ad_placement_gaps.json` + `transcript.json`, public video copy present, `result.json` with `video_file` + positive `scene_count`; `poster.jpg` present |

**Pre-`main()` failure detection (both runs):** a deliberately broken settings JSON crashes `run_job.py` at `json.loads` (line 29), before its `__main__` `try/except`; the probe observed **exit 1 with `status.json` still reading `queued`** — confirming the adapter contract that the child exit status is authoritative and `status.json` cannot be trusted for completion or failure.

## Verification (post-final-edit)

| Check | Result |
|---|---|
| Worker image rebuilt from clean context (`--no-cache`), smoke re-run | **pass** — exit 0, 93.6 s processing, 6.48 GiB peak, case B detected |
| `ruff check .` / `ruff format --check .` | pass / pass (55 files) |
| `pytest -q` | 56 passed |
| Frontend: `npm ci`, eslint, `tsc -b`, vitest, production build, demo build | all pass (0 errors; 2 pre-existing warnings) |
| Fixture preview smoke (demo dist serve + curl: index, scenes.json, video) | all 200 |
| `git diff --check` | clean |
| Image history/layer inspection | clean — layers are base/ffmpeg (457 MB)/pinned deps (1.43 GB)/baked weights (1.53 GB)/pipeline code (262 kB)/one allowlisted fixture (8.95 MB)/smoke script; config env holds no secrets (`GPG_KEY` is the python base image's public release-signing key); no `.env`, job data, or extra media entered the image |

## Conclusion

**G0 passes.** The existing pipeline runs unmodified inside a reproducible `linux/amd64` container against the committed fixture with the fake provider and audio ON, fully offline, with deterministic pinned dependencies and baked model weights. Two evidence-driven plan changes: worker task sizing is **2 vCPU/8 GB** (4 GB disproven by OOM; measured peak 6.57/6.48 GiB), and image-size risk is retired (2.04 GB actual vs 5–8 GB estimated). Residual unknowns move to the cloud smoke (G11): native-Fargate CPU timing, ECR pull time, and 5-minute-input peaks. **G1 (local stack scaffolding) is unblocked.**
