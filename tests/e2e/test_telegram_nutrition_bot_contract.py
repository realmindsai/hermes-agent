"""E2E contract tests for Telegram nutrition bot mode."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.platforms.base import MessageEvent, MessageType
from tests.e2e.conftest import make_adapter, make_event, make_runner, make_session_entry, make_source


class _FakeNutritionClient:
    def __init__(self):
        self.select_calls = []
        self.correct_calls = []

    def analyze_meal(self, payload):
        return {
            "candidate_set_id": "set-1",
            "candidates": [
                {"candidate_id": "cand-1", "title": "Chicken salad", "calories": 420},
                {"candidate_id": "cand-2", "title": "Tuna sandwich", "calories": 510},
            ],
        }

    def select_candidate(self, payload):
        self.select_calls.append(payload)
        return {"logged": True, "message": "Logged chicken salad."}

    def correct_candidate(self, payload):
        self.correct_calls.append(payload)
        return {"logged": True, "message": "Logged corrected meal."}


@pytest.fixture()
def nutrition_client():
    return _FakeNutritionClient()


@pytest.fixture()
def session_entry():
    return make_session_entry()


@pytest.fixture()
def runner(session_entry, nutrition_client):
    from gateway.nutrition_bridge import NutritionBridge
    from gateway.nutrition_state import NutritionStateStore

    runner = make_runner(session_entry)
    runner._update_prompt_pending = {}
    runner._running_agents_ts = {}
    runner.session_store._generate_session_key = lambda source: session_entry.session_key
    runner._nutrition_state_store = NutritionStateStore()
    runner._nutrition_bridge = NutritionBridge(
        state_store=runner._nutrition_state_store,
        client=nutrition_client,
    )
    return runner


@pytest.fixture()
def adapter(runner):
    adapter = make_adapter(runner)
    adapter._bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=321))
    )
    return adapter


@pytest.mark.asyncio
async def test_dm_photo_routes_to_bridge_and_sends_candidate_buttons(
    monkeypatch, runner, adapter
):
    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")
    event = MessageEvent(
        text="lunch",
        message_type=MessageType.PHOTO,
        source=make_source(),
        message_id="msg-photo-1",
        media_urls=["/tmp/lunch.jpg"],
    )
    session_key = runner._session_key_for_source(event.source)

    await adapter.handle_message(event)
    await asyncio.sleep(0.3)

    pending = runner._nutrition_state_store.get_pending_candidate_set(session_key)
    assert pending is not None
    assert pending["candidate_set_id"] == "set-1"
    adapter._bot.send_message.assert_awaited_once()
    kwargs = adapter._bot.send_message.await_args.kwargs
    assert kwargs["reply_markup"] is not None
    assert "Chicken salad" in kwargs["text"]


@pytest.mark.asyncio
async def test_nc_callback_is_routed_back_into_gateway_flow(
    monkeypatch, runner, adapter, nutrition_client
):
    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")
    session_key = runner._session_key_for_source(make_source())
    runner._nutrition_state_store.set_pending_candidate_set(
        session_key,
        candidate_set_id="set-1",
        candidates=[{"candidate_id": "cand-1", "title": "Chicken salad"}],
    )
    adapter.send.reset_mock()

    query = AsyncMock()
    query.data = "nc:set-1:cand-1"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 12345
    query.message.message_id = 456
    query.message.message_thread_id = None
    query.message.chat = MagicMock()
    query.message.chat.id = 12345
    query.message.chat.type = "private"
    query.message.chat.title = None
    query.message.chat.full_name = None
    query.from_user = MagicMock()
    query.from_user.id = 999
    query.from_user.full_name = "dew boi"

    update = MagicMock()
    update.callback_query = query

    await adapter._handle_callback_query(update, MagicMock())
    await asyncio.sleep(0.3)

    assert nutrition_client.select_calls == [
        {
            "session_id": session_key,
            "candidate_set_id": "set-1",
            "candidate_id": "cand-1",
        }
    ]
    adapter.send.assert_called_once()


@pytest.mark.asyncio
async def test_free_text_correction_uses_pending_candidate_context(
    monkeypatch, runner, adapter, nutrition_client
):
    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")
    session_key = runner._session_key_for_source(make_source())
    runner._nutrition_state_store.set_pending_candidate_set(
        session_key,
        candidate_set_id="set-1",
        candidates=[{"candidate_id": "cand-1", "title": "Chicken salad"}],
    )
    adapter.send.reset_mock()

    await adapter.handle_message(make_event("actually two eggs"))
    await asyncio.sleep(0.3)

    assert nutrition_client.correct_calls == [
        {
            "session_id": session_key,
            "candidate_set_id": "set-1",
            "correction_text": "actually two eggs",
        }
    ]
    adapter.send.assert_called_once()
