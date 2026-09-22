"""Unit tests for the SRT/CSV export writers."""

import exports as E


def test_timecode_srt_basic_and_clamp():
    assert E._timecode_srt(0) == "00:00:00,000"
    assert E._timecode_srt(3661.5) == "01:01:01,500"
    assert E._timecode_srt(-2) == "00:00:00,000"  # negative clamps to zero


def test_timecode_srt_millisecond_rollover():
    # 1.9999s rounds the ms field to 1000, which must carry into seconds.
    assert E._timecode_srt(1.9999) == "00:00:02,000"


def test_timecode_hms():
    assert E._timecode_hms(65) == "1:05"
    assert E._timecode_hms(3725) == "1:02:05"


def test_write_srt_only_active_nonempty_with_sequential_cues(tmp_path):
    scenes = [
        {"start": 1.0, "end": 2.0, "text": "first", "active": True},
        {"start": 3.0, "end": 4.0, "text": "skipped", "active": False},
        {"start": 5.0, "end": 6.0, "text": "   ", "active": True},  # empty after strip
        {"start": 7.0, "end": 8.0, "text": "second", "active": True},
    ]
    out = E.write_srt(scenes, tmp_path / "out.srt")
    content = out.read_text(encoding="utf-8")
    # Two cues, renumbered 1 and 2 (the inactive + empty scenes are dropped).
    assert "1\n00:00:01,000 --> 00:00:02,000\nfirst" in content
    assert "2\n00:00:07,000 --> 00:00:08,000\nsecond" in content
    assert "skipped" not in content
    assert content.count(" --> ") == 2


def test_write_csv_rows_flags_and_newline_stripping(tmp_path):
    scenes = [
        {
            "scene_id": "scene_1",
            "start": 1.0,
            "end": 3.5,
            "active": True,
            "voice": "onyx",
            "character_ids": ["char_1", "char_2"],
            "text": "line one\nline two",
        },
        {"scene_id": "scene_2", "start": 4.0, "end": 4.0, "active": False, "text": "x"},
    ]
    out = E.write_csv(scenes, tmp_path / "out.csv")
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("scene_id,start,end,duration,active")
    assert "1.000,3.500,2.500,1" in rows[1]
    assert "char_1;char_2" in rows[1]
    assert "line one line two" in rows[1]  # newline flattened to a space
    assert rows[2].endswith(",0,,,x")  # inactive flag is "0"
