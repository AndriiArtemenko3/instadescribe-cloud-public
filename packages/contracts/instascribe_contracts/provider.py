"""Server-controlled provider policy shared by the cloud API and worker.

The browser and queue contract never select a provider.  One deployment is
configured for exactly one of these backends, and the API stamps that value
onto every job so a differently configured worker can refuse the message
without claiming or mutating it.
"""

from typing import Final, Literal

ProviderName = Literal["fake", "openai"]

PROVIDER_ALLOWLIST: Final[tuple[ProviderName, ...]] = ("fake", "openai")
PROVIDER_MAX_ATTEMPTS: Final[dict[ProviderName, int]] = {"fake": 3, "openai": 1}

# The owner-approved G12 real-provider smoke is deliberately limited to a
# rights-cleared clip no longer than two minutes.
OPENAI_G12_MAX_DURATION_SECS: Final[int] = 120
