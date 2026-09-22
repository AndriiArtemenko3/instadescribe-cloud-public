import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from openai import OpenAI

load_dotenv(dotenv_path=Path(__file__).with_name(".env"))


def _bounded_env_int(name: str, default: int, *, maximum: int) -> int:
    """Parse a canonical positive integer without echoing hostile input."""
    raw = os.getenv(name)
    if raw is None:
        return default
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise RuntimeError(f"Invalid {name}")
    value = int(raw)
    if value > maximum:
        raise RuntimeError(f"Invalid {name}")
    return value


# Existing direct/local behavior remains unchanged when the environment is
# absent. The G12 worker supplies 6 and 8000 to its isolated OpenAI child.
MAX_CALLS = _bounded_env_int("INSTASCRIBE_MAX_PROVIDER_CALLS", 100, maximum=100)
DEFAULT_MAX_TOKENS = _bounded_env_int(
    "INSTASCRIBE_MAX_PROVIDER_OUTPUT_TOKENS", 20000, maximum=20000
)
_call_count = 0


def _bump():
    global _call_count
    _call_count += 1
    if _call_count > MAX_CALLS:
        raise RuntimeError(f"Exceeded MAX_CALLS={MAX_CALLS} (safety limit).")


def get_client() -> "OpenAI":
    # Lazy import keeps deterministic configuration helpers testable without
    # loading the provider SDK; production images still install it.
    from openai import OpenAI

    load_dotenv()
    base_url = os.getenv("OPENAI_BASE_URL")  # point at Ollama/vLLM/LM Studio/OpenRouter
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        if base_url:
            key = "not-needed"  # local OpenAI-compatible servers ignore the key
        else:
            raise RuntimeError("Missing OPENAI_API_KEY")
    return OpenAI(api_key=key, base_url=base_url or None)


def safe_create_response(client: "OpenAI", **kwargs):
    _bump()
    kwargs.setdefault("max_output_tokens", DEFAULT_MAX_TOKENS)
    return client.responses.create(**kwargs)
