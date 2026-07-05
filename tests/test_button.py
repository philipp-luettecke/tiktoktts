"""Tests for the Speak button (button.py).

The button reads the shared helper entities and dispatches a tts.speak call.
The tts.speak service is mocked so we can assert exactly what would be sent
without going near the network.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.tiktoktts.button import SpeakButtonEntity
from custom_components.tiktoktts.const import (
    ENTITY_ID_DEVICE,
    ENTITY_ID_LANGUAGE,
    ENTITY_ID_MESSAGE,
    ENTITY_ID_SPEAK,
    ENTITY_ID_TTS_DIRECT,
    ENTITY_ID_TTS_PROXY,
    ENTITY_ID_VOICE,
    RANDOM_SEED_KEY,
    RANDOM_VOICE_CODE,
    RANDOM_VOICE_LANG_NAME,
)

from .helpers import setup_direct, setup_proxy

KITCHEN = "media_player.kitchen"


def _mock_tts(hass: HomeAssistant) -> list[ServiceCall]:
    return async_mock_service(hass, "tts", "speak")


async def _set_message(hass: HomeAssistant, value: str) -> None:
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": ENTITY_ID_MESSAGE, "value": value},
        blocking=True,
    )


async def _press(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": ENTITY_ID_SPEAK}, blocking=True
    )


async def test_press_dispatches_tts_speak(hass: HomeAssistant) -> None:
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "Hello world")

    expected_voice = hass.states.get(ENTITY_ID_VOICE).attributes["code"]
    await _press(hass)

    assert len(calls) == 1
    data = calls[0].data
    assert data["message"] == "Hello world"
    assert data["media_player_entity_id"] == KITCHEN
    assert data["cache"] is True
    assert data["options"] == {"voice": expected_voice}
    # Proxy entity is the dispatch target.
    assert ENTITY_ID_TTS_PROXY in data["entity_id"]


async def test_press_with_empty_message_does_nothing(hass: HomeAssistant) -> None:
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "   ")  # whitespace only -> treated as empty
    await _press(hass)
    assert calls == []


async def test_press_with_unavailable_message_does_nothing(hass: HomeAssistant) -> None:
    """An unavailable message entity must not speak the literal 'unavailable'."""
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)
    calls = _mock_tts(hass)
    hass.states.async_set(ENTITY_ID_MESSAGE, "unavailable")
    await _press(hass)
    assert calls == []


async def test_press_without_voice_code_does_nothing(hass: HomeAssistant) -> None:
    """A voice entity without a 'code' attribute (not loaded yet) is rejected."""
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "Hello")
    hass.states.async_set(ENTITY_ID_VOICE, "Jessie")  # no attributes
    await _press(hass)
    assert calls == []


async def test_press_without_loaded_tts_entry_does_nothing(hass: HomeAssistant) -> None:
    """With all fields set but no loaded config entry, no tts.speak is sent."""
    calls = _mock_tts(hass)
    hass.states.async_set(ENTITY_ID_MESSAGE, "Hello")
    hass.states.async_set(ENTITY_ID_VOICE, "Jessie", {"code": "en_us_001"})
    hass.states.async_set(ENTITY_ID_DEVICE, "Kitchen", {"code": KITCHEN})

    button = SpeakButtonEntity()
    button.hass = hass
    await button.async_press()
    assert calls == []


async def test_press_with_helper_entities_missing_does_nothing(
    hass: HomeAssistant,
) -> None:
    """Missing helper entities (never created) resolve to empty values."""
    calls = _mock_tts(hass)
    button = SpeakButtonEntity()
    button.hass = hass
    await button.async_press()
    assert calls == []


async def test_press_without_device_does_nothing(hass: HomeAssistant) -> None:
    # No media_player exists, so the device select never resolves a target.
    await setup_proxy(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "Hello")
    await _press(hass)
    assert calls == []


async def test_direct_only_targets_direct_tts_entity(hass: HomeAssistant) -> None:
    """With only a direct entry configured, the button targets the direct entity."""
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_direct(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "Direct mode")
    await _press(hass)

    assert len(calls) == 1
    assert ENTITY_ID_TTS_DIRECT in calls[0].data["entity_id"]


async def test_both_modes_prefer_proxy(hass: HomeAssistant) -> None:
    """With both proxy and direct loaded, the button prefers the proxy entity."""
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)
    await setup_direct(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "Both modes")
    await _press(hass)

    assert len(calls) == 1
    assert ENTITY_ID_TTS_PROXY in calls[0].data["entity_id"]


async def test_random_voice_disables_cache_and_adds_seed(hass: HomeAssistant) -> None:
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)
    calls = _mock_tts(hass)
    await _set_message(hass, "Surprise me")

    # Configure a random pool, then select the Random Voice language option.
    await hass.services.async_call(
        "tiktoktts", "set_random_voices", {"languages": ["en_us"]}, blocking=True
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": ENTITY_ID_LANGUAGE, "option": RANDOM_VOICE_LANG_NAME},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID_VOICE).attributes["code"] == RANDOM_VOICE_CODE

    await _press(hass)

    assert len(calls) == 1
    data = calls[0].data
    assert data["cache"] is False
    assert data["options"]["voice"] == RANDOM_VOICE_CODE
    assert RANDOM_SEED_KEY in data["options"]
