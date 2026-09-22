import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ─── Paths ─────────────────────────────────────────────────────────────────────
# Env vars take priority (set by run_job.py for each job).
# Hardcoded values remain as fallbacks so CLI usage is fully backward-compatible.

_default_project_out = PROJECT_ROOT / "modular_pipeline_out" / "27 (test user prompt 3)"

VIDEO_ID = os.environ.get("JOB_VIDEO_ID", "video_001")
VIDEO_PATH = Path(os.environ.get("JOB_VIDEO_PATH", str(PROJECT_ROOT / "clips" / "vibe.mp4")))
FRAMES_DIR = Path(
    os.environ.get(
        "JOB_FRAMES_DIR", str(PROJECT_ROOT / "modular_pipeline" / "out_6" / "frames_vibe")
    )
)

# JOB_PROJECT_DIR sets the working directory for a job (memory, chunk outputs, reports).
# JOB_OUTPUT_DIR sets where the final frontend JSON files are written.
PROJECT_OUTPUT_DIR = Path(os.environ.get("JOB_PROJECT_DIR", str(_default_project_out)))
OUTPUT_DIR = Path(os.environ.get("JOB_OUTPUT_DIR", str(PROJECT_OUTPUT_DIR / "output")))
DEBUG_DIR = PROJECT_OUTPUT_DIR / "debug"

MEMORY_DIR = DEBUG_DIR / "memory"
RUNS_DIR = DEBUG_DIR / "chunk_outputs"
REPORTS_DIR = DEBUG_DIR / "reports"

MAX_AUDIO_EVENTS_PER_CHUNK = 10

# ─── Model / processing ────────────────────────────────────────────────────────

# user's prompt - goes to UI
USER_CUSTOM_PROMPT: str = os.environ.get(
    "JOB_PROMPT", "only focus on background, ignore the characters in the frames"
)

MODEL = os.environ.get("JOB_MODEL", "gpt-4.1")  # gpt-4.1 cheap testing, gpt-5.4 best production
IMAGE_DETAIL = os.environ.get("JOB_IMAGE_DETAIL", "low")

_chunk_sizes_env = os.environ.get("JOB_CHUNK_SIZES", "60")
CHUNK_SIZES = [int(x.strip()) for x in _chunk_sizes_env.split(",")]

MAX_PREVIOUS_SCENES = int(os.environ.get("JOB_MAX_PREVIOUS_SCENES", "15"))
MAX_KNOWN_CHARACTERS = int(os.environ.get("JOB_MAX_KNOWN_CHARACTERS", "20"))
SKIP_EXISTING = os.environ.get("JOB_SKIP_EXISTING", "false").lower() == "true"
STRICT_JSON_SCHEMA = os.environ.get("JOB_STRICT_JSON_SCHEMA", "true").lower() == "true"

SAVE_DEBUG_FILES = True
