"""Unit tests for HERMES_NUTRITION_BOT gate routing (run.py + telegram.py)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


# ── Telegram adapter: nc: callback fall-through ───────────────────────────────

@pytest.mark.asyncio
async def test_nc_callback_dispatched_to_handle_message():
    """nc: callbacks must reach handle_message (not be silently dropped)."""
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter._approval_state = {}
    adapter.platform = Platform.TELEGRAM

    dispatched = []

    async def capture(event):
        dispatched.append(event)

    adapter.set_message_handler(capture)

    query = MagicMock()
    query.data = "nc:set1:cand1"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 123
    query.message.message_id = 456
    query.from_user = MagicMock()
    query.from_user.id = 789
    query.from_user.first_name = "Dee"

    update = MagicMock()
    update.callback_query = query

    with patch.object(adapter, "handle_message", AsyncMock()) as mock_hm:
        await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once()            # Telegram loading spinner cleared
    mock_hm.assert_called_once()                 # dispatched to handle_message
    event_arg = mock_hm.call_args[0][0]
    assert event_arg.callback_data == "nc:set1:cand1"


@pytest.mark.asyncio
async def test_update_prompt_callback_not_dispatched_to_handle_message():
    """update_prompt: callbacks must NOT be re-dispatched — handled locally."""
    from gateway.platforms.telegram import TelegramAdapter

    adapter = object.__new__(TelegramAdapter)
    adapter._approval_state = {}
    adapter.platform = Platform.TELEGRAM
    adapter.set_message_handler(AsyncMock())

    query = MagicMock()
    query.data = "update_prompt:y"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.from_user = MagicMock()
    query.from_user.id = 1
    update = MagicMock()
    update.callback_query = query

    with patch.object(adapter, "handle_message", AsyncMock()) as mock_hm, \
         patch("hermes_constants.get_hermes_home", return_value=MagicMock()):
        await adapter._handle_callback_query(update, MagicMock())

    mock_hm.assert_not_called()  # update_prompt handled locally, not dispatched


# ── run.py gate routing ───────────────────────────────────────────────────────

def _make_runner_with_bridge(bridge_mock):
    """Minimal GatewayRunner with a pre-injected bridge mock."""
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner.config = MagicMock()
    runner.config.group_sessions_per_user = True
    runner.config.thread_sessions_per_user = False
    runner._nutrition_bridge = bridge_mock  # inject directly — bypasses lazy init
    return runner


def _dm_source(platform=Platform.TELEGRAM, chat_type="dm"):
    return SessionSource(
        platform=platform,
        chat_id="456",
        user_id="456",
        chat_type=chat_type,
    )


@pytest.mark.asyncio
async def test_gate_routes_photo_to_handle_photo_event():
    bridge = MagicMock()
    bridge.handle_photo_event = AsyncMock()
    runner = _make_runner_with_bridge(bridge)

    event = MessageEvent(text="", source=_dm_source(), media_urls=["file:///photo.jpg"])
    await runner._handle_nutrition_message(event, MagicMock())

    bridge.handle_photo_event.assert_called_once()


@pytest.mark.asyncio
async def test_gate_routes_nc_callback_to_handle_candidate_selection():
    bridge = MagicMock()
    bridge.handle_candidate_selection = AsyncMock()
    runner = _make_runner_with_bridge(bridge)

    event = MessageEvent(text="", source=_dm_source(), callback_data="nc:set1:cand1")
    await runner._handle_nutrition_message(event, MagicMock())

    bridge.handle_candidate_selection.assert_called_once()
    args = bridge.handle_candidate_selection.call_args[0]
    assert args[0] == "nc:set1:cand1"


@pytest.mark.asyncio
async def test_gate_routes_plain_text_to_handle_correction():
    bridge = MagicMock()
    bridge.handle_correction = AsyncMock()
    runner = _make_runner_with_bridge(bridge)

    event = MessageEvent(text="hello", source=_dm_source())
    await runner._handle_nutrition_message(event, MagicMock())

    bridge.handle_correction.assert_called_once()


@pytest.mark.asyncio
async def test_gate_drops_non_dm_silently():
    bridge = MagicMock()
    bridge.handle_photo_event = AsyncMock()
    bridge.handle_candidate_selection = AsyncMock()
    bridge.handle_correction = AsyncMock()
    runner = _make_runner_with_bridge(bridge)

    group_source = SessionSource(
        platform=Platform.TELEGRAM, chat_id="grp1", user_id="u1", chat_type="group"
    )
    event = MessageEvent(text="hi group", source=group_source)
    result = await runner._handle_nutrition_message(event, MagicMock())

    assert result is False
    bridge.handle_photo_event.assert_not_called()
    bridge.handle_candidate_selection.assert_not_called()
    bridge.handle_correction.assert_not_called()


@pytest.mark.asyncio
async def test_gate_drops_non_telegram_silently():
    bridge = MagicMock()
    bridge.handle_correction = AsyncMock()
    runner = _make_runner_with_bridge(bridge)

    discord_source = SessionSource(
        platform=Platform.DISCORD, chat_id="ch1", user_id="u1", chat_type="dm"
    )
    event = MessageEvent(text="hello", source=discord_source)
    result = await runner._handle_nutrition_message(event, MagicMock())

    assert result is False
    bridge.handle_correction.assert_not_called()


# ── _nutrition_bot_enabled gate ───────────────────────────────────────────────

def test_nutrition_bot_enabled_when_env_var_set(monkeypatch):
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")
    assert runner._nutrition_bot_enabled() is True


def test_nutrition_bot_disabled_by_default():
    import os
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    # Ensure env var is not set (use popitem or os.environ.pop safely)
    env_val = os.environ.pop("HERMES_NUTRITION_BOT", None)
    try:
        assert runner._nutrition_bot_enabled() is False
    finally:
        if env_val is not None:
            os.environ["HERMES_NUTRITION_BOT"] = env_val
