"""Unit tests for the TTS/AD-mix pure logic (no ffmpeg or network)."""

from pathlib import Path

import tts_render as T
from providers.openai_provider import OpenAITTSProvider


def test_openai_tts_voice_normalisation():
    tts = OpenAITTSProvider()
    assert tts._voice("NOVA") == "nova"
    assert tts._voice(" Onyx ") == "onyx"
    assert tts._voice("bogus") == "onyx"  # unknown → default
    assert tts._voice(None) == "onyx"
    assert tts._voice("echo") == "echo"


def test_clamp_speed():
    assert T.clamp_speed(1.0) == 1.0
    assert T.clamp_speed("1.5") == 1.5
    assert T.clamp_speed(None) == 1.0
    assert T.clamp_speed("not-a-number") == 1.0
    assert T.clamp_speed(99) == T.MAX_SPEED
    assert T.clamp_speed(0.01) == T.MIN_SPEED


def _block(start, duck, idx=0):
    return T.AdBlock(
        scene_id=f"scene_{idx}",
        start_secs=start,
        text="narration",
        voice="onyx",
        tts_path=Path(f"/tmp/ad{idx}.mp3"),
        tts_duration_secs=2.0,
        background_lufs=-20.0,
        apply_duck=duck,
    )


def test_build_filter_complex_sums_without_averaging():
    blocks = [_block(1.0, duck=True, idx=0), _block(5.0, duck=False, idx=1)]
    filter_str, out_label = T.build_filter_complex(blocks)

    assert out_label == "[aout]"
    # The bug fix: sum, never average, so the AD keeps its level.
    assert "amix=inputs=3:normalize=0" in filter_str
    assert "alimiter=limit=0.95[aout]" in filter_str
    # AD voices are delayed to their start and lifted by AD_GAIN.
    assert "adelay=1000|1000" in filter_str
    assert "adelay=5000|5000" in filter_str
    assert f"volume={T.AD_GAIN}" in filter_str


def test_build_filter_complex_ducks_only_flagged_windows():
    ducked = T.build_filter_complex([_block(1.0, duck=True)])[0]
    assert "volume=0.3:enable='between(t,1.0,3.0)'" in ducked

    not_ducked = T.build_filter_complex([_block(1.0, duck=False)])[0]
    assert "enable=" not in not_ducked  # no timeline-gated duck when the flag is off
