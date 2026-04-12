"""Tests for nutrition_client.py and MessageEvent.callback_data."""
from gateway.platforms.base import MessageEvent


def test_message_event_has_callback_data_field():
    """MessageEvent must accept callback_data for nc: routing."""
    event = MessageEvent(text="", callback_data="nc:set1:cand1")
    assert event.callback_data == "nc:set1:cand1"


def test_message_event_callback_data_defaults_to_none():
    event = MessageEvent(text="hello")
    assert event.callback_data is None


import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from gateway.nutrition_client import NutritionClient


def _resp(status_code: int, json_data=None) -> AsyncMock:
    """Build a response mock with a synchronous raise_for_status (mirrors httpx.Response)."""
    mock = AsyncMock()
    mock.status_code = status_code
    mock.json = lambda: json_data or {}
    mock.raise_for_status = MagicMock()  # httpx.Response.raise_for_status is sync
    return mock


@pytest.fixture
def http():
    """Mocked httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.mark.asyncio
async def test_analyze_sends_correct_payload(http):
    http.post.return_value = _resp(
        200,
        {"candidate_set_id": "set1", "candidates": [{"id": "c1", "label": "Apple 100g"}]},
    )
    nc = NutritionClient(client=http)
    result = await nc.analyze("sess1", [{"name": "apple", "confidence": 0.9}])

    http.post.assert_called_once_with(
        "http://172.17.0.1:8781/api/nutrition/v1/analyze",
        json={"session_id": "sess1", "observations": [{"name": "apple", "confidence": 0.9}]},
    )
    assert result["candidate_set_id"] == "set1"


@pytest.mark.asyncio
async def test_get_pending_returns_none_on_404(http):
    http.get.return_value = _resp(404)
    nc = NutritionClient(client=http)
    assert await nc.get_pending("sess1") is None


@pytest.mark.asyncio
async def test_get_pending_returns_data_on_200(http):
    http.get.return_value = _resp(200, {"candidate_set_id": "set1", "candidates": []})
    nc = NutritionClient(client=http)
    result = await nc.get_pending("sess1")
    assert result["candidate_set_id"] == "set1"


@pytest.mark.asyncio
async def test_select_sends_correct_payload(http):
    http.post.return_value = _resp(200, {"logged": True})
    nc = NutritionClient(client=http)
    result = await nc.select("sess1", "set1", "cand1")
    http.post.assert_called_once_with(
        "http://172.17.0.1:8781/api/nutrition/v1/select",
        json={"session_id": "sess1", "candidate_set_id": "set1", "candidate_id": "cand1"},
    )
    assert result["logged"] is True


@pytest.mark.asyncio
async def test_correct_sends_correct_payload(http):
    http.post.return_value = _resp(200, {"logged": True})
    nc = NutritionClient(client=http)
    result = await nc.correct("sess1", "set1", "grilled chicken 200g")
    http.post.assert_called_once_with(
        "http://172.17.0.1:8781/api/nutrition/v1/correct",
        json={
            "session_id": "sess1",
            "candidate_set_id": "set1",
            "correction_text": "grilled chicken 200g",
        },
    )
    assert result["logged"] is True


@pytest.mark.asyncio
async def test_base_url_from_env(monkeypatch, http):
    monkeypatch.setenv("NUTRITION_SERVICE_BASE_URL", "http://10.0.0.1:9999")
    http.post.return_value = _resp(200, {"candidate_set_id": "x", "candidates": []})
    nc = NutritionClient(client=http)
    await nc.analyze("s", [])
    assert http.post.call_args[0][0].startswith("http://10.0.0.1:9999")
