"""In-memory pending candidate-set state for Telegram nutrition mode."""

from __future__ import annotations

from typing import Any


class NutritionStateStore:
    """Track the current candidate set awaiting user input per session."""

    def __init__(self) -> None:
        self._pending_candidate_sets: dict[str, dict[str, Any]] = {}

    def set_pending_candidate_set(
        self,
        session_key: str,
        *,
        candidate_set_id: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        self._pending_candidate_sets[session_key] = {
            "candidate_set_id": candidate_set_id,
            "candidates": list(candidates or []),
        }

    def get_pending_candidate_set(self, session_key: str) -> dict[str, Any] | None:
        pending = self._pending_candidate_sets.get(session_key)
        if pending is None:
            return None
        return {
            "candidate_set_id": pending.get("candidate_set_id"),
            "candidates": list(pending.get("candidates") or []),
        }

    def clear_pending_candidate_set(self, session_key: str) -> None:
        self._pending_candidate_sets.pop(session_key, None)
