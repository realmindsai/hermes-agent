from pydantic import ValidationError

from nutrition_service.contracts import CandidateModel
from nutrition_service.resolution import choose_packaged_profile, rank_candidates


def test_candidate_model_accepts_required_fields():
    candidate = CandidateModel(
        candidate_id="cand-1",
        title="Protein bar",
        confidence=0.91,
        reason_text="matched wrapper text",
    )

    assert candidate.candidate_id == "cand-1"
    assert candidate.title == "Protein bar"
    assert candidate.confidence == 0.91
    assert candidate.reason_text == "matched wrapper text"


def test_candidate_model_rejects_missing_confidence():
    try:
        CandidateModel(
            candidate_id="cand-2",
            title="Protein bar",
            reason_text="matched wrapper text",
        )
    except ValidationError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for missing confidence")


def test_candidate_model_rejects_missing_reason_text():
    try:
        CandidateModel(
            candidate_id="cand-3",
            title="Protein bar",
            confidence=0.91,
        )
    except ValidationError as exc:
        assert "reason_text" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for missing reason_text")


def test_choose_packaged_profile_prefers_label_observation():
    chosen = choose_packaged_profile(
        label_profile={"profile_kind": "label_observation", "energy_kcal": 230},
        user_profile={"profile_kind": "user_confirmed", "energy_kcal": 220},
        off_profile={"profile_kind": "source_import", "energy_kcal": 210},
        usda_profile={"profile_kind": "source_import", "energy_kcal": 205},
    )

    assert chosen["profile_kind"] == "label_observation"
    assert chosen["energy_kcal"] == 230


def test_choose_packaged_profile_falls_back_by_precedence():
    chosen = choose_packaged_profile(
        label_profile=None,
        user_profile=None,
        off_profile={"profile_kind": "source_import", "energy_kcal": 210},
        usda_profile={"profile_kind": "source_import", "energy_kcal": 205},
    )

    assert chosen["profile_kind"] == "source_import"
    assert chosen["energy_kcal"] == 210


def test_rank_candidates_orders_by_confidence_then_reason_specificity():
    ranked = rank_candidates([
        {"title": "Chocolate bar", "confidence": 0.71, "reason_text": "generic visual guess"},
        {"title": "Carman's protein bar", "confidence": 0.88, "reason_text": "matched wrapper text"},
    ])

    assert ranked[0]["title"] == "Carman's protein bar"


def test_rank_candidates_prefers_longer_reason_when_confidence_ties():
    ranked = rank_candidates([
        {"title": "Bar A", "confidence": 0.9, "reason_text": "matched text"},
        {"title": "Bar B", "confidence": 0.9, "reason_text": "matched wrapper text exactly"},
    ])

    assert ranked[0]["title"] == "Bar B"
