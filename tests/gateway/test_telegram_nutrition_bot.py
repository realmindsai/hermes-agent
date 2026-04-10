"""Unit tests for Telegram nutrition bot gateway helpers."""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


def _ensure_telegram_mock() -> None:
    """Install minimal telegram mocks when python-telegram-bot is absent."""
    if "telegram" in sys.modules and hasattr(sys.modules["telegram"], "__file__"):
        return

    class _InlineKeyboardButton:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    class _InlineKeyboardMarkup:
        def __init__(self, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    telegram_mod = MagicMock()
    telegram_mod.InlineKeyboardButton = _InlineKeyboardButton
    telegram_mod.InlineKeyboardMarkup = _InlineKeyboardMarkup
    telegram_mod.constants.ParseMode.MARKDOWN = "Markdown"
    telegram_mod.constants.ParseMode.MARKDOWN_V2 = "MarkdownV2"
    telegram_mod.constants.ChatType.PRIVATE = "private"
    telegram_mod.constants.ChatType.GROUP = "group"
    telegram_mod.constants.ChatType.SUPERGROUP = "supergroup"
    telegram_mod.constants.ChatType.CHANNEL = "channel"
    telegram_mod.ext.ContextTypes.DEFAULT_TYPE = type(None)
    telegram_mod.error.NetworkError = type("NetworkError", (OSError,), {})
    telegram_mod.error.TimedOut = type("TimedOut", (OSError,), {})
    telegram_mod.error.BadRequest = type("BadRequest", (Exception,), {})

    for name in ("telegram", "telegram.ext", "telegram.constants", "telegram.request"):
        sys.modules.setdefault(name, telegram_mod)
    sys.modules.setdefault("telegram.error", telegram_mod.error)


_ensure_telegram_mock()

from gateway.config import PlatformConfig
from gateway.nutrition_bridge import build_candidate_rows
from gateway.nutrition_state import NutritionStateStore
from gateway.platforms.telegram import TelegramAdapter


def test_nutrition_state_store_round_trip():
    store = NutritionStateStore()

    store.set_pending_candidate_set(
        "session-1",
        candidate_set_id="set-1",
        candidates=[{"candidate_id": "cand-1", "title": "Protein bar"}],
    )

    assert store.get_pending_candidate_set("session-1") == {
        "candidate_set_id": "set-1",
        "candidates": [{"candidate_id": "cand-1", "title": "Protein bar"}],
    }

    store.clear_pending_candidate_set("session-1")

    assert store.get_pending_candidate_set("session-1") is None


def test_build_candidate_rows_uses_nc_callback_data(monkeypatch):
    class _Button:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    monkeypatch.setattr("gateway.nutrition_bridge.InlineKeyboardButton", _Button)

    rows = build_candidate_rows(
        "set-9",
        [
            {"candidate_id": "cand-1", "title": "Chicken salad"},
            {"candidate_id": "cand-2", "title": "Tuna sandwich"},
        ],
    )

    assert [button.text for row in rows for button in row] == ["Chicken salad", "Tuna sandwich"]
    assert [button.callback_data for row in rows for button in row] == [
        "nc:set-9:cand-1",
        "nc:set-9:cand-2",
    ]


@pytest.mark.asyncio
async def test_callback_query_routes_nc_data_into_internal_message_event(monkeypatch):
    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter.handle_message = AsyncMock()

    query = AsyncMock()
    query.data = "nc:set-1:cand-7"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 12345
    query.message.message_id = 678
    query.message.message_thread_id = None
    query.message.chat = MagicMock()
    query.message.chat.id = 12345
    query.message.chat.type = "private"
    query.message.chat.title = None
    query.message.chat.full_name = None
    query.from_user = MagicMock()
    query.from_user.id = 999
    query.from_user.full_name = "dw"

    update = MagicMock()
    update.callback_query = query

    await adapter._handle_callback_query(update, MagicMock())

    adapter.handle_message.assert_awaited_once()
    event = adapter.handle_message.await_args.args[0]
    assert event.text == "nc:set-1:cand-7"
    assert event.internal is True
    assert event.source.chat_id == "12345"
    assert event.source.user_id == "999"
    assert event.source.chat_type == "dm"
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_query_ignores_nc_data_when_nutrition_mode_is_off(monkeypatch):
    monkeypatch.delenv("HERMES_NUTRITION_BOT", raising=False)
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter.handle_message = AsyncMock()

    query = AsyncMock()
    query.data = "nc:set-1:cand-7"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 12345
    query.message.message_id = 678
    query.message.message_thread_id = None
    query.message.chat = MagicMock()
    query.message.chat.id = 12345
    query.message.chat.type = "private"
    query.message.chat.title = None
    query.message.chat.full_name = None
    query.from_user = MagicMock()
    query.from_user.id = 999
    query.from_user.full_name = "dw"

    update = MagicMock()
    update.callback_query = query

    await adapter._handle_callback_query(update, MagicMock())

    adapter.handle_message.assert_not_awaited()
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_query_ignores_nc_data_for_non_dm_chat(monkeypatch):
    monkeypatch.setenv("HERMES_NUTRITION_BOT", "1")
    adapter = TelegramAdapter(PlatformConfig(enabled=True, token="test-token"))
    adapter.handle_message = AsyncMock()

    query = AsyncMock()
    query.data = "nc:set-1:cand-7"
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = -10012345
    query.message.message_id = 678
    query.message.message_thread_id = None
    query.message.chat = MagicMock()
    query.message.chat.id = -10012345
    query.message.chat.type = "group"
    query.message.chat.title = "lunch crew"
    query.message.chat.full_name = None
    query.from_user = MagicMock()
    query.from_user.id = 999
    query.from_user.full_name = "dw"

    update = MagicMock()
    update.callback_query = query

    await adapter._handle_callback_query(update, MagicMock())

    adapter.handle_message.assert_not_awaited()
    query.answer.assert_awaited_once()
