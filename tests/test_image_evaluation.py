import copy

import pytest

from images.evaluation import (
    RELEASE_TARGETS,
    SCORE_FIELDS,
    ImageEvaluationError,
    build_blind_review_sheet,
    load_evaluation_cases,
    summarize_human_reviews,
)


def test_fixed_evaluation_set_validates_all_required_scenarios():
    cases = load_evaluation_cases()

    assert len(cases) >= 12
    assert sum(case["expected_safety"] == "allow" for case in cases) >= 10
    assert sum(case["expected_safety"] == "block" for case in cases) >= 2


def test_blind_review_sheet_excludes_provider_identity_and_blocked_prompts():
    cases = load_evaluation_cases()
    allowed = [case for case in cases if case["expected_safety"] == "allow"]
    anonymous_ids = {case["id"]: f"anonymous-{index}" for index, case in enumerate(allowed)}

    sheet = build_blind_review_sheet(cases, anonymous_ids)
    serialized = str(sheet).lower()

    assert len(sheet["rows"]) == len(allowed)
    assert "openrouter" not in serialized
    assert "gpt-image" not in serialized
    assert "gpt-5.6" not in serialized
    assert all(row["scores"] == {field: None for field in SCORE_FIELDS} for row in sheet["rows"])


def test_summary_requires_every_score_and_zero_critical_errors():
    passing_row = {
        "anonymous_id": "anonymous-1",
        "scores": {field: 100 for field in SCORE_FIELDS},
        "critical_error": False,
    }
    passing = summarize_human_reviews({"rows": [passing_row]})
    assert passing["release_ready"] is True
    assert passing["targets"] == RELEASE_TARGETS

    failing_row = copy.deepcopy(passing_row)
    failing_row["critical_error"] = True
    failing_row["scores"]["scientific_accuracy"] = 40
    failing = summarize_human_reviews({"rows": [failing_row]})
    assert failing["release_ready"] is False
    assert failing["critical_errors"] == 1
    assert failing["target_results"]["scientific_accuracy"] is False


def test_summary_rejects_incomplete_human_scores():
    row = {
        "anonymous_id": "anonymous-1",
        "scores": {field: 100 for field in SCORE_FIELDS},
        "critical_error": False,
    }
    row["scores"]["text_accuracy"] = None

    with pytest.raises(ImageEvaluationError, match="text_accuracy"):
        summarize_human_reviews({"rows": [row]})
