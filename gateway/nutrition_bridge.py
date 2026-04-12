"""Telegram-facing orchestration for the nutrition bot.

Intentionally Telegram-specific: uses InlineKeyboardMarkup directly
in _send_candidate_keyboard since this module is exclusively for the
Telegram DM nutrition flow.
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gateway.run import GatewayRunner
    from gateway.platforms.base import BasePlatformAdapter, MessageEvent

from gateway.nutrition_client import NutritionClient

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    _TELEGRAM_AVAILABLE = True
except ImportError:
    _TELEGRAM_AVAILABLE = False
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None

logger = logging.getLogger(__name__)

NUTRITION_SOUL = (
    "You are a nutrition logging assistant. When given a food photo, output ONLY "
    "a JSON array of observations: [{name, brand, barcode, quantity_g, confidence}]. "
    "Recall from memory any past meals matching what you see. "
    "No narrative. No questions. JSON only."
)

_MSG_UNAVAILABLE = "Nutrition service unavailable, try again shortly."
_MSG_SEND_PHOTO = "Send me a photo of your meal."
_MSG_LOGGED = "Logged!"
_MSG_UPDATED = "Updated!"
_MSG_BAD_PHOTO = "Couldn't read that photo, try again."


class NutritionBridge:
    """Routes Telegram nutrition events to nutrition-service via the Hermes agent loop."""

    def __init__(self, client: Optional[NutritionClient] = None) -> None:
        self._client = client or NutritionClient()

    async def handle_photo_event(
        self,
        event: "MessageEvent",
        session_key: str,
        runner: "GatewayRunner",
        adapter: "BasePlatformAdapter",
    ) -> None:
        """Analyse a food photo via the agent loop and present candidates."""
        chat_id = event.source.chat_id

        # Reject parallel photo submissions for the same session
        if getattr(runner, "_running_agents", None) and session_key in runner._running_agents:
            await adapter.send(chat_id, "Still processing your last photo, please wait…")
            return

        # Enrich message with vision descriptions so the agent can read the photo
        message_text = event.text or ""
        if event.media_urls:
            try:
                message_text = await runner._enrich_message_with_vision(
                    message_text, list(event.media_urls)
                )
            except Exception as exc:
                logger.error("Vision enrichment failed: %s", exc)
                await adapter.send(chat_id, _MSG_BAD_PHOTO)
                return

        # Run agent loop — agent sees vision-enriched description, SOUL constrains output to JSON
        try:
            result = await runner._run_agent(
                message=message_text,
                context_prompt=NUTRITION_SOUL,
                history=[],
                source=event.source,
                session_id=session_key,
            )
            raw = result.get("final_response", "") if isinstance(result, dict) else str(result)
        except Exception as exc:
            logger.error("Agent loop failed during nutrition photo analysis: %s", exc)
            await adapter.send(chat_id, _MSG_BAD_PHOTO)
            return

        # Strip markdown fences (model may wrap output in ```json ... ``` blocks)
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
            observations = json.loads(cleaned)
            if not isinstance(observations, list):
                raise ValueError("expected a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Malformed agent output: %s — raw: %r", exc, raw[:300])
            await adapter.send(chat_id, _MSG_BAD_PHOTO)
            return

        # Send to nutrition-service
        try:
            data = await self._client.analyze(session_key, observations)
        except Exception as exc:
            logger.error("nutrition-service analyze failed: %s", exc)
            await adapter.send(chat_id, _MSG_UNAVAILABLE)
            return

        candidate_set_id = data.get("candidate_set_id")
        if not candidate_set_id:
            logger.error("nutrition-service returned no candidate_set_id in analyze response")
            await adapter.send(chat_id, _MSG_UNAVAILABLE)
            return
        await self._send_candidate_keyboard(
            adapter, chat_id, candidate_set_id, data.get("candidates", [])
        )

    async def handle_candidate_selection(
        self,
        callback_data: str,
        session_key: str,
        adapter: "BasePlatformAdapter",
        chat_id: str,
    ) -> None:
        """Route an nc: callback to nutrition-service /select."""
        parts = callback_data.split(":", 2)
        if len(parts) != 3 or parts[0] != "nc":
            logger.warning("Malformed nc: callback ignored: %r", callback_data)
            return  # stale button — no reply

        _, candidate_set_id, candidate_id = parts
        try:
            await self._client.select(session_key, candidate_set_id, candidate_id)
        except Exception as exc:
            logger.error("nutrition-service select failed: %s", exc)
            await adapter.send(chat_id, _MSG_UNAVAILABLE)
            return
        await adapter.send(chat_id, _MSG_LOGGED)

    async def handle_correction(
        self,
        text: str,
        session_key: str,
        adapter: "BasePlatformAdapter",
        chat_id: str,
    ) -> None:
        """Route plain text to /correct if pending, else prompt for photo."""
        try:
            pending = await self._client.get_pending(session_key)
        except Exception as exc:
            logger.error("nutrition-service get_pending failed: %s", exc)
            await adapter.send(chat_id, _MSG_UNAVAILABLE)
            return

        if pending is None:
            await adapter.send(chat_id, _MSG_SEND_PHOTO)
            return

        candidate_set_id = pending.get("candidate_set_id") if isinstance(pending, dict) else None
        if not candidate_set_id:
            logger.error("nutrition-service pending response missing candidate_set_id")
            await adapter.send(chat_id, _MSG_UNAVAILABLE)
            return

        try:
            await self._client.correct(session_key, candidate_set_id, text)
        except Exception as exc:
            logger.error("nutrition-service correct failed: %s", exc)
            await adapter.send(chat_id, _MSG_UNAVAILABLE)
            return
        await adapter.send(chat_id, _MSG_UPDATED)

    async def _send_candidate_keyboard(
        self,
        adapter: "BasePlatformAdapter",
        chat_id: str,
        candidate_set_id: str,
        candidates: list[dict],
    ) -> None:
        """Render an inline keyboard with one button per candidate."""
        if not _TELEGRAM_AVAILABLE:
            logger.error("python-telegram-bot not installed; cannot send inline keyboard")
            await adapter.send(chat_id, "Keyboard unavailable — select item by replying with its name.")
            return

        if not candidates:
            await adapter.send(chat_id, _MSG_BAD_PHOTO)
            return

        buttons = []
        for c in candidates:
            cand_id = c.get("id")
            if not cand_id:
                logger.warning("candidate missing id field, skipping: %r", c)
                continue
            cb_data = f"nc:{candidate_set_id}:{cand_id}"
            if len(cb_data.encode()) > 64:
                logger.error(
                    "callback_data exceeds Telegram 64-byte limit (%d bytes); "
                    "nutrition-service IDs are too long",
                    len(cb_data.encode()),
                )
                await adapter.send(chat_id, _MSG_UNAVAILABLE)
                return
            buttons.append(
                InlineKeyboardButton(
                    text=c.get("label", cand_id),
                    callback_data=cb_data,
                )
            )
        if not buttons:
            await adapter.send(chat_id, _MSG_BAD_PHOTO)
            return
        await adapter._bot.send_message(
            chat_id=int(chat_id),
            text="Which one?",
            reply_markup=InlineKeyboardMarkup([buttons]),
        )
