"""Custom integration to integrate tiktoktts with Home Assistant.

For more details about this integration, please refer to
https://github.com/philipp-luettecke/tiktoktts
"""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = Platform.TTS

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Load TikTokTTS."""
    await hass.config_entries.async_forward_entry_setups(entry, [PLATFORMS])

    return True
