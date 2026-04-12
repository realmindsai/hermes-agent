"""Tests for nutrition_client.py and MessageEvent.callback_data."""
from gateway.platforms.base import MessageEvent


def test_message_event_has_callback_data_field():
    """MessageEvent must accept callback_data for nc: routing."""
    event = MessageEvent(text="", callback_data="nc:set1:cand1")
    assert event.callback_data == "nc:set1:cand1"


def test_message_event_callback_data_defaults_to_none():
    event = MessageEvent(text="hello")
    assert event.callback_data is None
