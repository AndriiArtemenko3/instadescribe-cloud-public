"""Tests for the AD-quality evaluation harness (Python side).

Uses the shared fixture tests/fixtures/eval_sample.json — the same file the
vitest mirror loads — so the two implementations are pinned to one expected score.
"""

import json
import pathlib

import evaluation

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "eval_sample.json"


def _load():
    return json.loads(FIXTURE.read_text())


def _evaluate():
    d = _load()
    return evaluation.evaluate_ad(d["scenes"], d["audioEvents"], d["entities"], d["durationSecs"])


def test_dimension_scores_match_expected():
    r = _evaluate()
    assert r["active_count"] == 4  # 2 of 6 scenes excluded (inactive + empty)
    assert r["dimensions"] == {
        "timing": 0.75,
        "dialogue_safety": 0.75,
        "coverage": 0.8,
        "character_consistency": 0.75,
        "grounding": 0.5,
    }
    assert r["overall"] == 0.72  # shared cross-language expected value


def test_flags_identify_problem_scenes():
    by_id = {f["scene_id"]: set(f["issues"]) for f in _evaluate()["flags"]}
    assert by_id["scene_1"] == {"dialogue_collision", "duplicate_text"}
    assert by_id["scene_2"] == {"narration_too_long"}
    assert by_id["scene_3"] == {"orphan_character", "duplicate_text"}
    assert "scene_4" not in by_id  # the clean scene carries no flags


def test_empty_input_scores_zero():
    r = evaluation.evaluate_ad([], [], [], 10)
    assert r["overall"] == 0.0 and r["active_count"] == 0
    assert all(v == 0.0 for v in r["dimensions"].values())
