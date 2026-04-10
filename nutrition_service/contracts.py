from pydantic import BaseModel


class CandidateModel(BaseModel):
    candidate_id: str
    title: str
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    confidence: float
    reason_text: str
