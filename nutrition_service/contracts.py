from typing import Annotated

from pydantic import BaseModel, Field


class CandidateModel(BaseModel):
    candidate_id: str
    title: str
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    confidence: Annotated[float, Field(strict=True, allow_inf_nan=False)]
    reason_text: str
