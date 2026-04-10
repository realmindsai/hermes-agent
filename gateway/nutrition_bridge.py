"""Telegram nutrition-bot bridge helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nutrition_service.client import NutritionServiceClient

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
except ImportError:
    class InlineKeyboardButton:  # type: ignore[override]
        def __init__(self, text: str, callback_data: str | None = None):
            self.text = text
            self.callback_data = callback_data

    class InlineKeyboardMarkup:  # type: ignore[override]
        def __init__(self, inline_keyboard: list[list[InlineKeyboardButton]]):
            self.inline_keyboard = inline_keyboard


logger = logging.getLogger(__name__)


def build_candidate_rows(
    candidate_set_id: str,
    candidates: list[dict[str, Any]],
) -> list[list[InlineKeyboardButton]]:
    """Build one Telegram inline-button row per candidate."""
    rows: list[list[InlineKeyboardButton]] = []
    for candidate in candidates or []:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        title = str(candidate.get("title") or candidate_id).strip() or candidate_id
        rows.append(
            [
                InlineKeyboardButton(
                    text=title[:64],
                    callback_data=f"nc:{candidate_set_id}:{candidate_id}",
                )
            ]
        )
    return rows


class NutritionBridge:
    """Route Telegram nutrition-bot interactions to the nutrition service."""

    def __init__(self, state_store, client: NutritionServiceClient | None = None) -> None:
        self._state_store = state_store
        self._client = client or NutritionServiceClient()

    async def handle_photo_event(self, event, session_key: str, adapter=None) -> str | None:
        payload = {
            "session_id": session_key,
            "caption_text": (event.text or "").strip(),
            "image_paths": list(event.media_urls or []),
        }
        result = await asyncio.to_thread(self._client.analyze_meal, payload)
        candidate_set_id = str(result.get("candidate_set_id") or "").strip()
        candidates = list(result.get("candidates") or [])

        if candidate_set_id and candidates:
            self._state_store.set_pending_candidate_set(
                session_key,
                candidate_set_id=candidate_set_id,
                candidates=candidates,
            )
        else:
            self._state_store.clear_pending_candidate_set(session_key)

        reply_text = self._format_candidates_reply(result)
        if candidate_set_id and candidates and await self._send_candidate_reply(
            adapter=adapter,
            event=event,
            reply_text=reply_text,
            candidate_set_id=candidate_set_id,
            candidates=candidates,
        ):
            return None
        return reply_text

    async def handle_candidate_selection(self, event, session_key: str) -> str:
        pending = self._state_store.get_pending_candidate_set(session_key)
        if not pending:
            return "No pending nutrition candidate set for this chat."

        parsed = self._parse_callback_data(event.text or "")
        if parsed is None:
            return "That nutrition selection is invalid."
        candidate_set_id, candidate_id = parsed
        if candidate_set_id != pending.get("candidate_set_id"):
            self._state_store.clear_pending_candidate_set(session_key)
            return "That nutrition selection is stale. Send the meal photo again."

        result = await asyncio.to_thread(
            self._client.select_candidate,
            {
                "session_id": session_key,
                "candidate_set_id": candidate_set_id,
                "candidate_id": candidate_id,
            },
        )
        self._state_store.clear_pending_candidate_set(session_key)
        return self._result_message(result, fallback="Logged nutrition selection.")

    async def handle_correction(self, event, session_key: str) -> str:
        pending = self._state_store.get_pending_candidate_set(session_key)
        if not pending:
            return "No pending nutrition candidate set for this chat."

        result = await asyncio.to_thread(
            self._client.correct_candidate,
            {
                "session_id": session_key,
                "candidate_set_id": pending.get("candidate_set_id"),
                "correction_text": (event.text or "").strip(),
            },
        )
        self._state_store.clear_pending_candidate_set(session_key)
        return self._result_message(result, fallback="Logged corrected meal.")

    async def _send_candidate_reply(
        self,
        *,
        adapter,
        event,
        reply_text: str,
        candidate_set_id: str,
        candidates: list[dict[str, Any]],
    ) -> bool:
        bot = getattr(adapter, "_bot", None)
        if bot is None:
            return False

        try:
            kwargs = {
                "chat_id": self._coerce_numeric(getattr(event.source, "chat_id", None)),
                "text": reply_text,
                "parse_mode": None,
                "reply_markup": InlineKeyboardMarkup(
                    build_candidate_rows(candidate_set_id, candidates)
                ),
            }
            if getattr(event, "message_id", None):
                kwargs["reply_to_message_id"] = self._coerce_numeric(event.message_id)
            if getattr(event.source, "thread_id", None):
                kwargs["message_thread_id"] = self._coerce_numeric(event.source.thread_id)
            await bot.send_message(**kwargs)
            return True
        except Exception as exc:
            logger.warning("Failed to send Telegram nutrition candidate buttons: %s", exc)
            return False

    @staticmethod
    def _coerce_numeric(value: Any) -> Any:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return value

    @staticmethod
    def _parse_callback_data(raw: str) -> tuple[str, str] | None:
        parts = str(raw or "").split(":", 2)
        if len(parts) != 3 or parts[0] != "nc":
            return None
        candidate_set_id = parts[1].strip()
        candidate_id = parts[2].strip()
        if not candidate_set_id or not candidate_id:
            return None
        return candidate_set_id, candidate_id

    def _format_candidates_reply(self, result: dict[str, Any]) -> str:
        candidates = list(result.get("candidates") or [])
        if not candidates:
            return self._result_message(
                result,
                fallback="I couldn't build a nutrition candidate list from that photo.",
            )

        lines = ["Pick the closest meal, or reply with a correction:"]
        for index, candidate in enumerate(candidates, start=1):
            title = str(candidate.get("title") or f"Candidate {index}")
            calories = candidate.get("calories")
            if calories is None:
                lines.append(f"{index}. {title}")
            else:
                lines.append(f"{index}. {title} ({calories} cal)")
        return "\n".join(lines)

    @staticmethod
    def _result_message(result: dict[str, Any], *, fallback: str) -> str:
        message = str(result.get("message") or "").strip()
        if message:
            return message
        if result.get("logged") is True:
            return fallback
        return fallback
