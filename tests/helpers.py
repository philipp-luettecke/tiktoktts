"""Shared helpers for entity tests that need a fully set-up config entry."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tiktoktts.const import (
    API_MODE_DIRECT,
    API_MODE_PROXY,
    CONF_API_MODE,
    CONF_ENDPOINT,
    CONF_SESSION_ID,
    CONF_VOICE,
    DEFAULT_PROXY_ENDPOINT,
    DEFAULT_VOICE,
    DIRECT_API_ENDPOINTS,
    DOMAIN,
)


async def setup_proxy(
    hass: HomeAssistant, voice: str = DEFAULT_VOICE
) -> MockConfigEntry:
    """Add and set up a proxy config entry, returning the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_MODE: API_MODE_PROXY,
            CONF_ENDPOINT: DEFAULT_PROXY_ENDPOINT,
            CONF_VOICE: voice,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def setup_direct(
    hass: HomeAssistant, voice: str = DEFAULT_VOICE
) -> MockConfigEntry:
    """Add and set up a direct config entry, returning the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_MODE: API_MODE_DIRECT,
            CONF_ENDPOINT: DIRECT_API_ENDPOINTS[0],
            CONF_SESSION_ID: "sessionid-abc123",
            CONF_VOICE: voice,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
