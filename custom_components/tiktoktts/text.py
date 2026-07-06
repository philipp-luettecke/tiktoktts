"""Text entity for TikTok TTS - shared message input field.

One shared text entity (text.tiktoktts_message) exists for the whole
integration; the owning config entry forwards this platform (see
__init__.py). Readable in dashboard templates via:

  message: "{{ states('text.tiktoktts_message') }}"
"""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ENTITY_ID_MESSAGE,
    ENTITY_NAME_MESSAGE,
    LOGGER,
    UNIQUE_ID_MESSAGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the shared message text entity for the owning config entry."""
    async_add_entities([MessageTextEntity()])
    LOGGER.debug("Shared text entity created for entry %s", config_entry.entry_id)


class MessageTextEntity(TextEntity, RestoreEntity):
    """Shared text input for the TTS message - one instance for the whole integration.

    Provides a native HA text input field in Lovelace without requiring the
    user to create an input_text helper. Readable in templates via:

      {{ states('text.tiktoktts_message') }}
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_icon = "mdi:message-text"
    _attr_native_max = 255
    _attr_unique_id = UNIQUE_ID_MESSAGE
    _attr_name = ENTITY_NAME_MESSAGE

    def __init__(self) -> None:
        """Initialise with an empty message."""
        self.entity_id = ENTITY_ID_MESSAGE
        self._attr_native_value = ""

    async def async_added_to_hass(self) -> None:
        """Restore the last message text from the HA state database."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (
            None,
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            self._attr_native_value = last_state.state
            LOGGER.debug(
                "Message restored: %s",
                last_state.state[:50] + "..."
                if len(last_state.state) > 50
                else last_state.state,
            )

    async def async_set_value(self, value: str) -> None:
        """Handle the user typing a new message."""
        self._attr_native_value = value
        self.async_write_ha_state()
        LOGGER.debug(
            "Message updated: %s",
            value[:50] + "..." if len(value) > 50 else value,
        )
