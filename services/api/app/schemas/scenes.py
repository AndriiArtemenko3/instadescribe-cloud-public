"""Scene-override PATCH contract (G6 Gate 3).

A non-empty STRICT subset of the editable fields. Unknown fields and
client-supplied `version` are forbidden; explicit null is invalid (omitted
and null are NOT equivalent); booleans must be JSON booleans; speed must be
a finite JSON number in [0.5, 2.5]. Nothing is clamped or silently ignored.
"""

import math
import re

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, field_validator, model_validator

SCENE_ID_RE = re.compile(r"^scene_[1-9][0-9]*$")
VOICE_ALLOWLIST = ("onyx", "nova", "alloy", "shimmer", "echo", "fable")
MAX_AD_CHARS = 8000
# NUL and unsafe C0 controls are rejected; \t \n \r stay legal in AD text.
_UNSAFE_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Wire field -> scene_overrides column (ad is stored in `text`).
WIRE_TO_COLUMN = {
    "ad": "text",
    "active": "active",
    "locked": "locked",
    "voice": "voice",
    "speed": "speed",
}


class SceneOverridePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ad: StrictStr | None = None
    active: StrictBool | None = None
    locked: StrictBool | None = None
    voice: StrictStr | None = None
    speed: float | None = None

    @field_validator("ad")
    @classmethod
    def _ad_bounded_and_safe(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) > MAX_AD_CHARS:
            raise ValueError(f"ad must be at most {MAX_AD_CHARS} characters")
        if _UNSAFE_CONTROL_RE.search(v):
            raise ValueError("ad contains unsupported control characters")
        return v

    @field_validator("voice")
    @classmethod
    def _voice_allowed(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in VOICE_ALLOWLIST:
            raise ValueError("voice not in the approved allowlist")
        return v

    @field_validator("speed", mode="before")
    @classmethod
    def _speed_strict_finite_bounded(cls, v):
        if v is None:
            return None
        # bool is an int subclass; strings/objects are coercions — all rejected.
        if isinstance(v, bool) or not isinstance(v, int | float):
            raise ValueError("speed must be a JSON number")
        try:
            # G6.1: a valid JSON integer with hundreds of digits overflows
            # float() — that is a normal validation failure, never a 500.
            value = float(v)
        except OverflowError:
            raise ValueError("speed must be within [0.5, 2.5]") from None
        if not math.isfinite(value):
            raise ValueError("speed must be finite")
        if not 0.5 <= value <= 2.5:
            raise ValueError("speed must be within [0.5, 2.5]")
        # G6.1 precision contract: the column is NUMERIC(4,2); accepting
        # 2.499 would silently store 2.50. Reject more than two decimal
        # places — nothing is clamped, rounded or silently altered.
        from decimal import Decimal

        if -Decimal(str(value)).as_tuple().exponent > 2:
            raise ValueError("speed supports at most two decimal places")
        return value

    @model_validator(mode="after")
    def _non_empty_strict_subset(self) -> "SceneOverridePatch":
        provided = self.model_fields_set
        if not provided:
            raise ValueError("at least one editable field is required")
        # Explicit null is invalid: omitted and null are NOT equivalent.
        for field in provided:
            if getattr(self, field) is None:
                raise ValueError(f"{field} may not be null; omit it instead")
        return self

    def column_values(self) -> dict:
        """Only the fields present in THIS request, keyed by column name."""
        return {WIRE_TO_COLUMN[field]: getattr(self, field) for field in self.model_fields_set}
