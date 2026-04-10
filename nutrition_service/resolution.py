from collections.abc import Mapping, Sequence
import math
from typing import Any


def _normalized_words(text: str) -> set[str]:
    return {
        word
        for word in str(text or "").lower().replace("/", " ").replace("-", " ").split()
        if word
    }


def _score_title_match(*, caption_text: str, title: str, source_name: str) -> tuple[float, str]:
    caption = str(caption_text or "").strip().lower()
    title_text = str(title or "").strip()
    title_lower = title_text.lower()
    overlap = len(_normalized_words(caption) & _normalized_words(title_text))
    phrase_match = bool(caption and title_lower and title_lower in caption)
    base_scores = {
        "off": 0.45,
        "usda": 0.40,
        "fsanz": 0.35,
    }
    confidence = base_scores.get(source_name, 0.30)
    if overlap:
        confidence += min(0.30, overlap * 0.15)
    if phrase_match:
        confidence += 0.20
    confidence = min(confidence, 0.99)
    if overlap or phrase_match:
        return confidence, f"matched caption text against {source_name.upper()} source data"
    return confidence, f"fallback {source_name.upper()} source candidate"


def build_source_candidates(
    *,
    caption_text: str,
    off_rows: Sequence[Mapping[str, Any]],
    fsanz_rows: Sequence[Mapping[str, Any]],
    usda_rows: Sequence[Mapping[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for row in off_rows:
        title = " ".join(
            part.strip()
            for part in (str(row.get("brand_name") or ""), str(row.get("product_name") or ""))
            if part and part.strip()
        )
        if not title:
            continue
        confidence, reason_text = _score_title_match(
            caption_text=caption_text,
            title=title,
            source_name="off",
        )
        candidates.append(
            {
                "candidate_id": f"off:{row.get('id')}",
                "title": title,
                "calories": row.get("energy_kcal"),
                "protein_g": row.get("protein_g"),
                "carbs_g": row.get("carbs_g"),
                "fat_g": row.get("fat_g"),
                "confidence": confidence,
                "reason_text": reason_text,
            }
        )

    for row in fsanz_rows:
        title = str(row.get("food_name") or "").strip()
        if not title:
            continue
        confidence, reason_text = _score_title_match(
            caption_text=caption_text,
            title=title,
            source_name="fsanz",
        )
        candidates.append(
            {
                "candidate_id": f"fsanz:{row.get('id')}",
                "title": title,
                "calories": row.get("energy_kcal"),
                "protein_g": row.get("protein_g"),
                "carbs_g": row.get("carbs_g"),
                "fat_g": row.get("fat_g"),
                "confidence": confidence,
                "reason_text": reason_text,
            }
        )

    for row in usda_rows:
        title = str(row.get("description") or "").strip()
        if not title:
            continue
        confidence, reason_text = _score_title_match(
            caption_text=caption_text,
            title=title,
            source_name="usda",
        )
        candidates.append(
            {
                "candidate_id": f"usda:{row.get('id')}",
                "title": title,
                "calories": row.get("energy_kcal"),
                "protein_g": row.get("protein_g"),
                "carbs_g": row.get("carbs_g"),
                "fat_g": row.get("fat_g"),
                "confidence": confidence,
                "reason_text": reason_text,
            }
        )

    return rank_candidates(candidates)[:limit]


def choose_packaged_profile(label_profile, user_profile, off_profile, usda_profile):
    for profile in (label_profile, user_profile, off_profile, usda_profile):
        if profile is not None:
            return profile
    return None


def _candidate_value(candidate: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(field_name, default)
    return getattr(candidate, field_name, default)


def _candidate_confidence(candidate: Any) -> float:
    raw_confidence = _candidate_value(candidate, "confidence", 0.0)
    if isinstance(raw_confidence, bool) or isinstance(raw_confidence, str):
        return 0.0
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(confidence):
        return 0.0
    return confidence


def rank_candidates(candidates: Sequence[Any]) -> list[Any]:
    return sorted(
        candidates,
        key=lambda candidate: (-_candidate_confidence(candidate), -len(str(_candidate_value(candidate, "reason_text", "") or "").strip())),
    )
