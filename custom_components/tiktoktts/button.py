"""Button entity for TikTok TTS - the Speak button.

One shared button entity (button.tiktoktts_speak) exists for the whole
integration; the owning config entry forwards this platform (see
__init__.py). When pressed it reads the current state of the other shared
entities - text.tiktoktts_message (state), select.tiktoktts_voice and
select.tiktoktts_device (both via their 'code' attribute) - and calls
tts.speak directly in Python, so no templates or scripts are needed.

TTS entity selection: the target is derived from loaded config entries
(ConfigEntryState.LOADED) rather than hass.states, which can hold stale
entries for previously removed config entries. Proxy mode is preferred over
direct mode when both are configured.

Random voice: when the selected voice code is RANDOM_VOICE_CODE, caching is
disabled and a unique _random_seed is passed in the options dict. HA hashes
all supported_options keys into the TTS cache key, so the unique seed forces
a cache miss and a fresh random voice on every press.
"""

from __future__ import annotations

from uuid import uuid4

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    API_MODE_DIRECT,
    API_MODE_PROXY,
    CONF_API_MODE,
    DOMAIN,
    ENTITY_ID_DEVICE,
    ENTITY_ID_MESSAGE,
    ENTITY_ID_SPEAK,
    ENTITY_ID_TTS_DIRECT,
    ENTITY_ID_TTS_PROXY,
    ENTITY_ID_VOICE,
    ENTITY_NAME_SPEAK,
    LOGGER,
    PLACEHOLDER_LOADING,
    RANDOM_SEED_KEY,
    RANDOM_VOICE_CODE,
    TTS_SERVICE_DOMAIN,
    TTS_SERVICE_FIELD_CACHE,
    TTS_SERVICE_FIELD_MESSAGE,
    TTS_SERVICE_FIELD_OPTIONS,
    TTS_SERVICE_FIELD_PLAYER,
    TTS_SERVICE_FIELD_VOICE,
    TTS_SERVICE_SPEAK,
    UNIQUE_ID_SPEAK,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the shared Speak button for the owning config entry."""
    async_add_entities([SpeakButtonEntity()])
    LOGGER.debug("Shared button entity created for entry %s", config_entry.entry_id)


class SpeakButtonEntity(ButtonEntity):
    """Speak button - reads the shared helper entities and calls tts.speak.

    Handles everything server-side in Python, avoiding the HA frontend
    limitation where button cards cannot evaluate templates in data fields.
    """

    _attr_has_entity_name = False
    _attr_icon = "mdi:microphone"
    _attr_unique_id = UNIQUE_ID_SPEAK
    _attr_name = ENTITY_NAME_SPEAK

    def __init__(self) -> None:
        """Initialise the speak button."""
        self.entity_id = ENTITY_ID_SPEAK

    async def async_press(self) -> None:
        """Handle button press - read helper entities and call tts.speak.

        Reads current values from:
          text.tiktoktts_message  -> state value  (the message text)
          select.tiktoktts_voice  -> 'code' attr  (the raw API voice code)
          select.tiktoktts_device -> 'code' attr  (the raw media_player entity_id)

        Voice and device use the 'code' attribute rather than state because
        their dropdowns display friendly names while storing API values in
        the attribute.

        When random voice is selected, caching is disabled and a unique
        _random_seed is passed in the options to force a cache miss.
        """
        # Strip whitespace - the card sends a single space when the textarea
        # is empty (HA text entity rejects truly empty strings), so we must
        # strip before checking to avoid speaking a silent space.
        message = self._get_state(ENTITY_ID_MESSAGE).strip()
        voice = self._get_code(ENTITY_ID_VOICE)
        device = self._get_code(ENTITY_ID_DEVICE)

        if not message:
            LOGGER.warning(
                "TikTokTTS Speak button pressed but message is empty. "
                "Type a message in the TikTokTTS Message field first."
            )
            return

        if not voice or voice == PLACEHOLDER_LOADING:
            LOGGER.warning("TikTokTTS Speak button pressed but no voice is selected.")
            return

        if not device or device == PLACEHOLDER_LOADING:
            LOGGER.warning(
                "TikTokTTS Speak button pressed but no output device is selected."
            )
            return

        tts_entity = self._pick_tts_entity()
        if not tts_entity:
            LOGGER.error(
                "TikTokTTS Speak button pressed but no TikTokTTS TTS entity "
                "was found. Make sure the integration is configured."
            )
            return

        use_cache = voice != RANDOM_VOICE_CODE
        options_dict = {TTS_SERVICE_FIELD_VOICE: voice}
        if voice == RANDOM_VOICE_CODE:
            options_dict[RANDOM_SEED_KEY] = str(uuid4())

        LOGGER.debug(
            "Speak button: entity=%s device=%s voice=%s cache=%s message=%s",
            tts_entity,
            device,
            voice,
            use_cache,
            message[:50] + "..." if len(message) > 50 else message,
        )

        await self.hass.services.async_call(
            domain=TTS_SERVICE_DOMAIN,
            service=TTS_SERVICE_SPEAK,
            service_data={
                TTS_SERVICE_FIELD_PLAYER: device,
                TTS_SERVICE_FIELD_MESSAGE: message,
                TTS_SERVICE_FIELD_CACHE: use_cache,
                TTS_SERVICE_FIELD_OPTIONS: options_dict,
            },
            target={"entity_id": tts_entity},
        )

    def _get_state(self, entity_id: str) -> str:
        """Return the current state of an entity, or empty string if unavailable.

        Filters out STATE_UNKNOWN and STATE_UNAVAILABLE so callers never
        accidentally speak the literal string "unavailable" or "unknown".
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            LOGGER.warning("TikTokTTS: entity %s not found in hass.states", entity_id)
            return ""
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return ""
        return state.state

    def _get_code(self, entity_id: str) -> str:
        """Return the 'code' attribute of an entity - the underlying API value.

        Voice and device selects display friendly names as their state but
        store the raw API code (voice ID or media_player entity_id) in the
        'code' attribute. This method reads that attribute directly.
        """
        state = self.hass.states.get(entity_id)
        if state is None:
            LOGGER.warning("TikTokTTS: entity %s not found in hass.states", entity_id)
            return ""
        code = state.attributes.get("code", "")
        if not code:
            LOGGER.warning(
                "TikTokTTS: entity %s has no 'code' attribute - "
                "it may not have finished loading yet.",
                entity_id,
            )
        return code

    def _pick_tts_entity(self) -> str | None:
        """Pick the TTS entity to use - proxy preferred over direct.

        Checks loaded config entries only (ConfigEntryState.LOADED) rather
        than hass.states, which may contain stale entries from previously
        removed config entries.
        """
        modes = {
            entry.data.get(CONF_API_MODE, API_MODE_PROXY)
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.state == ConfigEntryState.LOADED
        }
        if API_MODE_PROXY in modes:
            return ENTITY_ID_TTS_PROXY
        if API_MODE_DIRECT in modes:
            return ENTITY_ID_TTS_DIRECT
        return None
