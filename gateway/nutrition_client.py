"""Async HTTP client for the standalone nutrition-service.

No business logic. All four methods map 1:1 to nutrition-service endpoints.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://172.17.0.1:8781"


class NutritionClient:
    """Thin async HTTP client for nutrition-service API v1."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("NUTRITION_SERVICE_BASE_URL", _DEFAULT_BASE_URL)
        ).rstrip("/")
        self._client = client  # injected in tests; lazy-created in production

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def analyze(self, session_id: str, observations: list[dict]) -> dict:
        """POST /api/nutrition/v1/analyze — send observations, receive candidates."""
        r = await self._http.post(
            f"{self.base_url}/api/nutrition/v1/analyze",
            json={"session_id": session_id, "observations": observations},
        )
        r.raise_for_status()
        return r.json()

    async def select(
        self, session_id: str, candidate_set_id: str, candidate_id: str
    ) -> dict:
        """POST /api/nutrition/v1/select — log a candidate selection."""
        r = await self._http.post(
            f"{self.base_url}/api/nutrition/v1/select",
            json={
                "session_id": session_id,
                "candidate_set_id": candidate_set_id,
                "candidate_id": candidate_id,
            },
        )
        r.raise_for_status()
        return r.json()

    async def correct(
        self, session_id: str, candidate_set_id: str, correction_text: str
    ) -> dict:
        """POST /api/nutrition/v1/correct — log a free-text correction."""
        r = await self._http.post(
            f"{self.base_url}/api/nutrition/v1/correct",
            json={
                "session_id": session_id,
                "candidate_set_id": candidate_set_id,
                "correction_text": correction_text,
            },
        )
        r.raise_for_status()
        return r.json()

    async def get_pending(self, session_id: str) -> dict | None:
        """GET /api/nutrition/v1/pending/{session_id}.

        Returns None on 404 (no pending set). Raises for other errors.
        """
        r = await self._http.get(
            f"{self.base_url}/api/nutrition/v1/pending/{session_id}",
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
