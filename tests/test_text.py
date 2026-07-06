"""Tests for the shared message text entity (text.py)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.tiktoktts.const import ENTITY_ID_MESSAGE

from .helpers import setup_proxy


async def test_message_starts_empty(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    assert hass.states.get(ENTITY_ID_MESSAGE).state == ""


async def test_set_value_updates_state(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    await hass.services.async_call(
        "text",
        "set_value",
        {"entity_id": ENTITY_ID_MESSAGE, "value": "Dinner is ready"},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID_MESSAGE).state == "Dinner is ready"


async def test_message_restored_after_restart(hass: HomeAssistant) -> None:
    mock_restore_cache(hass, (State(ENTITY_ID_MESSAGE, "remembered message"),))
    await setup_proxy(hass)
    assert hass.states.get(ENTITY_ID_MESSAGE).state == "remembered message"


async def test_message_max_length_attribute(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    assert hass.states.get(ENTITY_ID_MESSAGE).attributes["max"] == 255
