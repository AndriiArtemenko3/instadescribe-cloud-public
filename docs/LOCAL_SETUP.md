# Local setup for the preserved Cloud Core snapshot

Run commands from the repository root unless stated otherwise. Use Node.js 22.19+
and Python 3.12. These are three distinct execution paths.

## 1. Keyless fixture demo

```bash
cd App
npm ci
npm run demo
```

This builds pre-generated fixture mode and serves it on localhost:4173. No Flask,
FastAPI, database, model credentials or AWS account is required. It does not prove
live generation or cloud availability.

## 2. Original local Flask/media pipeline

Requires FFmpeg on PATH, Python 3.12, model-provider credentials or separately installed
local models. The full Python dependencies include the media/ML stack and are heavier
than the test environment.

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env locally: choose the backend and supply only your own credentials.
npm --prefix App ci
npm --prefix App run build
```

Start the unchanged legacy server bound to loopback:

```bash
PYTHONPATH=modular_pipeline python -c 'from server import app; app.run(host="127.0.0.1", port=8765, threaded=True, debug=False)'
```

Open http://127.0.0.1:8765. Do not publish this unauthenticated legacy server.
The historical `make server` command binds all interfaces; the loopback command
above is preferred for this public snapshot. See [provider setup](local-models.md)
for optional local/provider requirements. Fixture success does not verify real inference.

## 3. Cloud architecture locally: FastAPI + PostgreSQL + LocalStack

Requires a running Docker engine and Compose. The default services bind host ports
5432, 4566 and 8000 to loopback; stop if those ports belong to another project.

```bash
docker compose up --build -d --wait
```

This starts PostgreSQL, LocalStack, a one-shot migration and FastAPI. It does not start
the media worker. For the frontend, in another terminal:

```bash
cd App
npm ci
npx vite --mode cloud --host 127.0.0.1
```

The development cloud client defaults to the local API on port 8000. Enter the
explicitly non-production portfolio token `local-dev-token` when requested. Compose
uses documented dummy credentials; never substitute production credentials into Git.

For asynchronous processing, the existing worker is an explicit opt-in and its image
is considerably heavier (linux/amd64, media/ML dependencies, 8 GiB memory limit):

```bash
docker compose --profile worker up --build -d --wait
```

The default worker/provider path is deterministic; this is not an AWS deployment.
Cloud TTS/Smart Fill/export are unavailable in v0.1. Stop local services without
removing their volumes with `docker compose --profile worker stop`.

## Python and integration checks

Lightweight root checks, in a separate Python 3.12 environment:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest -q
```

API checks need the API dependency lock and a migrated PostgreSQL service.
Running `pytest services/api/tests -q` without services is not a supported full check:
one route test still queries PostgreSQL even when integration flags are unset.
Use the service-backed commands below or GitHub CI.

For the full API/worker integration suites, first start the local cloud services;
install `uv` and use the existing guarded Make targets:

```bash
make cloud-test
make g5-test
```

These create a separate test-designated database. Never point integration tests at
an application or production database. The existing [CI workflow](../.github/workflows/ci.yml)
provides the PostgreSQL/LocalStack environment for the API checks.

Terraform setup and the historical manual deployment sequence are preserved in the
[infrastructure README](../infrastructure/terraform/portfolio/README.md). They are
not needed for local review. Do not run an AWS plan/apply merely to try the demo.
