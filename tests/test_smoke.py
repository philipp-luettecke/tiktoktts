"""Smoke test: the integration imports and sets up from a config entry."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.tiktoktts.const import (
    DOMAIN,
    ENTITY_ID_DEVICE,
    ENTITY_ID_LANGUAGE,
    ENTITY_ID_MESSAGE,
    ENTITY_ID_SPEAK,
    ENTITY_ID_TTS_PROXY,
    ENTITY_ID_VOICE,
)


async def test_setup_and_entities_created(hass: HomeAssistant, proxy_entry) -> None:
    """A proxy config entry loads and creates the TTS + shared entities."""
    proxy_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(proxy_entry.entry_id)
    await hass.async_block_till_done()

    assert proxy_entry.state is ConfigEntryState.LOADED

    # The per-entry TTS entity and all four shared singletons should exist.
    for entity_id in (
        ENTITY_ID_TTS_PROXY,
        ENTITY_ID_LANGUAGE,
        ENTITY_ID_VOICE,
        ENTITY_ID_DEVICE,
        ENTITY_ID_MESSAGE,
        ENTITY_ID_SPEAK,
    ):
        assert hass.states.get(entity_id) is not None, entity_id

    # The custom set_random_voices service is registered in async_setup.
    assert hass.services.has_service(DOMAIN, "set_random_voices")
