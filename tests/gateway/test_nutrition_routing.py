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
