from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nutrition_service.contracts import CandidateModel
from nutrition_service.resolution import build_source_candidates
from nutrition_service.models import (
    AnalysisRequest,
    ImageAsset,
    MealCandidate,
    MealLog,
    SourceFoodFsanz,
    SourceFoodUsda,
    SourceProductOff,
)


class NutritionService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("session_id") or "").strip()
        caption_text = str(payload.get("caption_text") or "").strip()
        image_paths = [str(path).strip() for path in list(payload.get("image_paths") or []) if str(path).strip()]

        with self._session_factory() as session:
            analysis_request = AnalysisRequest(
                session_id=session_id,
                caption_text=caption_text or None,
                status="completed",
            )
            session.add(analysis_request)
            session.flush()

            for image_path in image_paths:
                session.add(
                    ImageAsset(
                        analysis_request_id=analysis_request.id,
                        storage_path=image_path,
                    )
                )

            candidates = build_source_candidates(
                caption_text=caption_text,
                off_rows=self._source_rows(
                    session,
                    select(
                        SourceProductOff.id,
                        SourceProductOff.product_name,
                        SourceProductOff.brand_name,
                        SourceProductOff.energy_kcal,
                        SourceProductOff.protein_g,
                        SourceProductOff.carbs_g,
                        SourceProductOff.fat_g,
                    ),
                ),
                fsanz_rows=self._source_rows(
                    session,
                    select(
                        SourceFoodFsanz.id,
                        SourceFoodFsanz.food_name,
                        SourceFoodFsanz.energy_kcal,
                        SourceFoodFsanz.protein_g,
                        SourceFoodFsanz.carbs_g,
                        SourceFoodFsanz.fat_g,
                    ),
                ),
                usda_rows=self._source_rows(
                    session,
                    select(
                        SourceFoodUsda.id,
                        SourceFoodUsda.description,
                        SourceFoodUsda.energy_kcal,
                        SourceFoodUsda.protein_g,
                        SourceFoodUsda.carbs_g,
                        SourceFoodUsda.fat_g,
                    ),
                ),
            )

            validated_candidates = [
                CandidateModel(**candidate).model_dump()
                for candidate in candidates
            ]

            for candidate in validated_candidates:
                session.add(
                    MealCandidate(
                        analysis_request_id=analysis_request.id,
                        candidate_id=candidate["candidate_id"],
                        candidate_title=candidate["title"],
                        reason_text=candidate["reason_text"],
                        confidence=candidate["confidence"],
                        calories=candidate.get("calories"),
                        protein_g=candidate.get("protein_g"),
                        carbs_g=candidate.get("carbs_g"),
                        fat_g=candidate.get("fat_g"),
                    )
                )

            session.commit()

            return {
                "candidate_set_id": str(analysis_request.id),
                "candidates": validated_candidates,
            }

    def select_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_set_id = self._parse_analysis_request_id(payload.get("candidate_set_id"))
        candidate_id = str(payload.get("candidate_id") or "").strip()

        with self._session_factory() as session:
            analysis_request = session.get(AnalysisRequest, candidate_set_id)
            candidate = session.scalar(
                select(MealCandidate).where(
                    MealCandidate.analysis_request_id == candidate_set_id,
                    MealCandidate.candidate_id == candidate_id,
                )
            )
            if analysis_request is None or candidate is None:
                return {"logged": False, "message": "Nutrition candidate not found."}

            analysis_request.status = "selected"
            session.add(
                MealLog(
                    analysis_request_id=analysis_request.id,
                    title=candidate.candidate_title,
                    calories=candidate.calories,
                )
            )
            session.commit()
            return {"logged": True, "message": f"Logged {candidate.candidate_title}."}

    def correct_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidate_set_id = self._parse_analysis_request_id(payload.get("candidate_set_id"))
        correction_text = str(payload.get("correction_text") or "").strip()

        with self._session_factory() as session:
            analysis_request = session.get(AnalysisRequest, candidate_set_id)
            if analysis_request is None:
                return {"logged": False, "message": "Nutrition candidate not found."}

            analysis_request.status = "corrected"
            session.add(
                MealLog(
                    analysis_request_id=analysis_request.id,
                    title=correction_text,
                    calories=None,
                )
            )
            session.commit()
            return {"logged": True, "message": "Logged corrected meal."}

    @staticmethod
    def _source_rows(session: Session, statement) -> list[dict[str, Any]]:
        return [dict(row._mapping) for row in session.execute(statement).all()]

    @staticmethod
    def _parse_analysis_request_id(raw_value: Any) -> int | None:
        try:
            return int(str(raw_value).strip())
        except (TypeError, ValueError):
            return None
