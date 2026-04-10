"""Integration tests for Telegram nutrition bot gateway interception."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.base import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.session import SessionSource, build_session_key


class _FakeNutritionClient:
    def __init__(self):
        self.analyze_calls = []
        self.select_calls = []
        self.correct_calls = []

    def analyze_meal(self, payload):
        self.analyze_calls.append(payload)
        return {
            "candidate_set_id": "set-1",
            "candidates": [
                {
                    "candidate_id": "cand-1",
                    "title": "Chicken salad",
                    "calories": 420,
                }
            ],
        }

    def select_candidate(self, payload):
        self.select_calls.append(payload)
        return {"logged": True, "message": "Logged chicken salad."}

    def correct_candidate(self, payload):
        self.correct_calls.append(payload)
        return {"logged": True, "message": "Logged corrected meal."}


def _make_runner(client):
    from gateway.nutrition_bridge import NutritionBridge
    from gateway.nutrition_state import NutritionStateStore

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig()
    runner.adapters = {}
    runner._update_prompt_pending = {}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner.session_store = SimpleNamespace(
        _generate_session_key=lambda source: build_session_key(source)
    )
    runner._is_user_authorized = lambda _source: True
    runner._handle_message_with_agent = AsyncMock(return_value="normal-path")
    runner._nutrition_state_store = NutritionStateStore()
    runner._nutrition_bridge = NutritionBridge(
        state_store=runner._nutrition_state_store,
        client=client,
    )
    return runner


def _make_source(chat_type="dm"):
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        user_id="999",
        user_name="dw",
        chat_type=chat_type,
    )


@pytest.mark.asyncio
async def test_dm_photo_routes_to_bridge_and_stores_pending_candidate_set(monkeypatch):
    client = _FakeNutritionClient()
    runner = _make_runner(client)
    adapter = SimpleNamespace(
        _bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=77))
        ),
        send=AsyncMock(),
    )
    runner.adapters[Platform.TELEGRAM] = adapter
    event = MessageEvent(
        text="lunch",
        message_type=MessageType.PHOTO,
        source=_make_source(),
        message_id="m-1",
        media_urls=["/tmp/lunch.jpg"],
    )
    session_key = runner._session_key_for_source(event.source)

    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")

    result = await runner._handle_message(event)

    assert result is None
    assert client.analyze_calls == [
        {
            "session_id": session_key,
            "caption_text": "lunch",
            "image_paths": ["/tmp/lunch.jpg"],
        }
    ]
    assert runner._nutrition_state_store.get_pending_candidate_set(session_key) == {
        "candidate_set_id": "set-1",
        "candidates": [
            {
                "candidate_id": "cand-1",
                "title": "Chicken salad",
                "calories": 420,
            }
        ],
    }
    adapter._bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_nc_callback_text_uses_pending_candidate_set(monkeypatch):
    client = _FakeNutritionClient()
    runner = _make_runner(client)
    runner.adapters[Platform.TELEGRAM] = SimpleNamespace(
        _bot=SimpleNamespace(send_message=AsyncMock()),
        send=AsyncMock(),
    )
    source = _make_source()
    session_key = runner._session_key_for_source(source)
    runner._nutrition_state_store.set_pending_candidate_set(
        session_key,
        candidate_set_id="set-1",
        candidates=[{"candidate_id": "cand-1", "title": "Chicken salad"}],
    )
    event = MessageEvent(text="nc:set-1:cand-1", source=source, internal=True)

    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")

    result = await runner._handle_message(event)

    assert result == "Logged chicken salad."
    assert client.select_calls == [
        {
            "session_id": session_key,
            "candidate_set_id": "set-1",
            "candidate_id": "cand-1",
        }
    ]
    assert runner._nutrition_state_store.get_pending_candidate_set(session_key) is None


@pytest.mark.asyncio
async def test_free_text_correction_uses_pending_candidate_set(monkeypatch):
    client = _FakeNutritionClient()
    runner = _make_runner(client)
    runner.adapters[Platform.TELEGRAM] = SimpleNamespace(
        _bot=SimpleNamespace(send_message=AsyncMock()),
        send=AsyncMock(),
    )
    source = _make_source()
    session_key = runner._session_key_for_source(source)
    runner._nutrition_state_store.set_pending_candidate_set(
        session_key,
        candidate_set_id="set-1",
        candidates=[{"candidate_id": "cand-1", "title": "Chicken salad"}],
    )
    event = MessageEvent(text="actually two eggs", source=source)

    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")

    result = await runner._handle_message(event)

    assert result == "Logged corrected meal."
    assert client.correct_calls == [
        {
            "session_id": session_key,
            "candidate_set_id": "set-1",
            "correction_text": "actually two eggs",
        }
    ]
    assert runner._nutrition_state_store.get_pending_candidate_set(session_key) is None


@pytest.mark.asyncio
async def test_group_photo_falls_through_to_normal_runner(monkeypatch):
    client = _FakeNutritionClient()
    runner = _make_runner(client)
    runner.adapters[Platform.TELEGRAM] = SimpleNamespace(
        _bot=SimpleNamespace(send_message=AsyncMock()),
        send=AsyncMock(),
    )
    event = MessageEvent(
        text="group lunch",
        message_type=MessageType.PHOTO,
        source=_make_source(chat_type="group"),
        media_urls=["/tmp/group.jpg"],
    )

    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")

    result = await runner._handle_message(event)

    assert result == "normal-path"
    assert client.analyze_calls == []
