from dataclasses import dataclass


@dataclass(slots=True)
class CandidateModel:
    candidate_id: str
    title: str
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    confidence: float = 0.0
    reason_text: str = ""
