"""Model-provider seam for the three model-backed pipeline stages.

Call sites import the factory, never a vendor SDK:

    from providers import get_vision_provider, get_text_provider, get_tts_provider

Backend is chosen at runtime from environment variables (see factory.py).
"""

from .base import (
    CaptionResult,
    Frame,
    ProviderError,
    TextProvider,
    TextResult,
    TTSProvider,
    VisionProvider,
)
from .factory import (
    VALID_BACKENDS,
    active_backend,
    get_text_provider,
    get_tts_provider,
    get_vision_provider,
    provider_status,
    set_active_backend,
)

__all__ = [
    "VALID_BACKENDS",
    "CaptionResult",
    "Frame",
    "ProviderError",
    "TextProvider",
    "TextResult",
    "TTSProvider",
    "VisionProvider",
    "active_backend",
    "get_text_provider",
    "get_tts_provider",
    "get_vision_provider",
    "provider_status",
    "set_active_backend",
]
