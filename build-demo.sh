#!/usr/bin/env bash
# Build the public zero-API demo / tutorial frontend.
#
# Every OpenAI/TTS/render call is short-circuited to committed fixtures or local
# computation (see App/src/lib/demoApi.ts), so this build needs no API key and no
# backend. Unlike build-study.sh, it KEEPS dist/data + dist/videos — in the demo
# those static fixtures ARE the backend.
set -euo pipefail

cd "$(dirname "$0")/App"

VITE_DEMO_MODE=1 \
VITE_API_BASE="" \
npm run build

echo ""
echo "Built App/dist (demo mode: no key, no backend)."
echo "Serve it:  cd App && npm run preview    # or: npx serve -s App/dist"
echo "One-shot from the repo root:  make demo"
