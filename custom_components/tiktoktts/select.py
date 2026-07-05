"""Select entities for TikTok TTS - language, voice, and device dropdowns.

One set of these entities is shared across all config entries; the owning
entry forwards this platform (see __init__.py) so no singleton guard is
needed here.

Language / Voice coordination
-----------------------------
The two dropdowns never hold references to each other. They coordinate
through helpers.dispatcher and one hass.data key:

  * The language entity writes its current code to
    hass.data[DOMAIN][HASS_DATA_CURRENT_LANGUAGE] and sends
    SIGNAL_LANGUAGE_CHANGED whenever it changes (including once after
    restoring state on startup).
  * The voice entity applies the stored code when it is added and reacts to
    the signal afterwards. Because each entity both publishes its state and
    reads the other's on arrival, the startup ordering of the two entities
    does not matter.

A voice restored from the previous run is kept in _pending_restore_voice and
applied the first time the options list is rebuilt for the restored language.

Random Voice
------------
When the pool (managed by the tiktoktts.set_random_voices service) is
non-empty, a "Random Voice" option appears at the top of the language
dropdown; selecting it collapses the voice dropdown to a single "Random
Voice" entry. The service handler broadcasts SIGNAL_RANDOM_POOL_UPDATED and
the language entity rebuilds its options in response. The actual voice is
resolved at speak time in tts.py.

Device select
-------------
Populated from hass.states, showing friendly names in the dropdown with the
raw media_player entity_id exposed via the 'code' state attribute. The list
refreshes when a player appears, disappears, or changes availability.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ALL_VOICES,
    CONF_VOICE,
    DEFAULT_LANG,
    DEFAULT_VOICE,
    DOMAIN,
    ENTITY_ID_DEVICE,
    ENTITY_ID_LANGUAGE,
    ENTITY_ID_VOICE,
    ENTITY_NAME_DEVICE,
    ENTITY_NAME_LANGUAGE,
    ENTITY_NAME_VOICE,
    HASS_DATA_CURRENT_LANGUAGE,
    HASS_DATA_RANDOM_LANGS,
    LANGUAGE_ALL_CODE,
    LANGUAGE_ALL_NAME,
    LANGUAGE_NAMES,
    LOGGER,
    PLACEHOLDER_LOADING,
    RANDOM_VOICE_CODE,
    RANDOM_VOICE_LANG_NAME,
    RANDOM_VOICE_NAME,
    SIGNAL_LANGUAGE_CHANGED,
    SIGNAL_RANDOM_POOL_UPDATED,
    SUPPORTED_LANGUAGES,
    UNIQUE_ID_DEVICE,
    UNIQUE_ID_LANGUAGE,
    UNIQUE_ID_VOICE,
    VOICE_NAMES,
    VOICES_BY_LANGUAGE,
)


def _lang_to_name(code: str) -> str:
    """Convert a language code to its friendly display name."""
    if code == LANGUAGE_ALL_CODE:
        return LANGUAGE_ALL_NAME
    if code == RANDOM_VOICE_CODE:
        return RANDOM_VOICE_LANG_NAME
    return LANGUAGE_NAMES.get(code, code)


def _name_to_lang(name: str) -> str:
    """Convert a friendly language name back to its API code."""
    if name == LANGUAGE_ALL_NAME:
        return LANGUAGE_ALL_CODE
    if name == RANDOM_VOICE_LANG_NAME:
        return RANDOM_VOICE_CODE
    for code, friendly in LANGUAGE_NAMES.items():
        if friendly == name:
            return code
    return name


def _voice_to_name(code: str) -> str:
    """Convert a voice API code to its friendly display name.

    e.g. "en_male_narration" -> "Story Teller". The raw API code is exposed
    separately via the 'code' state attribute.
    """
    return VOICE_NAMES.get(code, code)


def _language_for_voice(voice: str) -> str:
    """Return the language group a voice belongs to, or the default language."""
    for lang, voices in VOICES_BY_LANGUAGE.items():
        if voice in voices:
            return lang
    return DEFAULT_LANG


def _sort_voices(codes: list[str]) -> dict[str, str]:
    """Return an ordered {friendly_label: voice_code} map, sorted by label.

    Using a mapping instead of two index-aligned lists keeps each label
    coupled to its API code structurally, so a future edit cannot silently
    misalign them.
    """
    paired = sorted(
        ((c, _voice_to_name(c)) for c in codes),
        key=lambda x: x[1].lower(),
    )
    return {name: code for code, name in paired}


def _usable(state: State | None) -> bool:
    """Return True if a media_player state can be used as a TTS target."""
    return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the shared select entities for the owning config entry."""
    default_voice = config_entry.data.get(CONF_VOICE, DEFAULT_VOICE)
    async_add_entities(
        [
            LanguageSelectEntity(default_voice),
            VoiceSelectEntity(default_voice),
            DeviceSelectEntity(),
        ]
    )
    LOGGER.debug("Shared select entities created for entry %s", config_entry.entry_id)


class LanguageSelectEntity(SelectEntity, RestoreEntity):
    """Shared language dropdown - one instance for the whole integration.

    Displays friendly names like "🇺🇸 English (US)". The raw language code is
    exposed via the 'code' state attribute and broadcast to the voice entity
    via SIGNAL_LANGUAGE_CHANGED.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_icon = "mdi:translate"
    _attr_unique_id = UNIQUE_ID_LANGUAGE
    _attr_name = ENTITY_NAME_LANGUAGE

    def __init__(self, default_voice: str) -> None:
        """Initialise with the language derived from the configured default voice."""
        self.entity_id = ENTITY_ID_LANGUAGE
        self._attr_options = [LANGUAGE_ALL_NAME] + [
            _lang_to_name(c) for c in SUPPORTED_LANGUAGES
        ]
        self._current_code = _language_for_voice(default_voice)
        self._attr_current_option = _lang_to_name(self._current_code)

    async def async_added_to_hass(self) -> None:
        """Restore the last language and publish it for the voice entity.

        The random-voice option is refreshed first (without a state write) so
        a restored "Random Voice" state passes the options validation below.
        The final dispatcher send covers the case where the voice entity was
        added before this entity; if it arrives later instead, it reads the
        published code from hass.data on its own.
        """
        await super().async_added_to_hass()
        self._refresh_random_voice_option(write_state=False)

        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self._attr_options:
            code = _name_to_lang(last_state.state)
            if (
                code in (LANGUAGE_ALL_CODE, RANDOM_VOICE_CODE)
                or code in SUPPORTED_LANGUAGES
            ):
                self._current_code = code
                self._attr_current_option = last_state.state
                LOGGER.debug("Language restored to: %s", last_state.state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RANDOM_POOL_UPDATED, self._handle_pool_updated
            )
        )
        self._publish_language()

    @callback
    def _publish_language(self) -> None:
        """Write the current code to hass.data and notify the voice entity."""
        self.hass.data.setdefault(DOMAIN, {})[HASS_DATA_CURRENT_LANGUAGE] = (
            self._current_code
        )
        async_dispatcher_send(self.hass, SIGNAL_LANGUAGE_CHANGED, self._current_code)

    @callback
    def _handle_pool_updated(self) -> None:
        """Rebuild options when the random-voice pool changes."""
        self._refresh_random_voice_option()

    @callback
    def _refresh_random_voice_option(self, write_state: bool = True) -> None:
        """Add or remove the Random Voice option based on the current pool.

        With write_state=False (startup), the options list is rebuilt without
        writing state - the entity is not fully registered yet. If the pool
        becomes empty while Random Voice is selected, the selection falls back
        to the default language so the entity never holds an invalid state.
        """
        langs = self.hass.data.get(DOMAIN, {}).get(HASS_DATA_RANDOM_LANGS, [])
        base_options = [LANGUAGE_ALL_NAME] + [
            _lang_to_name(c) for c in SUPPORTED_LANGUAGES
        ]
        if langs:
            base_options = [RANDOM_VOICE_LANG_NAME] + base_options
        self._attr_options = base_options

        prev_code = self._current_code
        if self._current_code == RANDOM_VOICE_CODE and not langs:
            self._current_code = DEFAULT_LANG
            self._attr_current_option = _lang_to_name(DEFAULT_LANG)

        if write_state:
            self.async_write_ha_state()
            if self._current_code != prev_code:
                self._publish_language()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw code, the random pool, and the code<->name map.

        language_options lets the dashboard card build its checkbox list from
        API codes without duplicating the name table client-side.
        """
        langs = []
        if self.hass:
            langs = self.hass.data.get(DOMAIN, {}).get(HASS_DATA_RANDOM_LANGS, [])
        return {
            "code": self._current_code,
            "random_voice_languages": langs,
            "language_options": [
                {"code": c, "name": _lang_to_name(c)} for c in SUPPORTED_LANGUAGES
            ],
        }

    async def async_select_option(self, option: str) -> None:
        """Handle language selection and notify the voice entity."""
        code = _name_to_lang(option)
        if (
            code not in (LANGUAGE_ALL_CODE, RANDOM_VOICE_CODE)
            and code not in SUPPORTED_LANGUAGES
        ):
            LOGGER.warning("Unknown language selected: %s", option)
            return
        self._current_code = code
        self._attr_current_option = option
        self.async_write_ha_state()
        self._publish_language()
        LOGGER.debug("Language changed to: %s (%s)", option, code)


class VoiceSelectEntity(SelectEntity, RestoreEntity):
    """Shared voice dropdown - one instance for the whole integration.

    Displays friendly names like "Story Teller"; the raw API code is exposed
    via the 'code' state attribute, which button.py reads when calling
    tts.speak. Options are filtered to the currently selected language.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_icon = "mdi:microphone"
    _attr_unique_id = UNIQUE_ID_VOICE
    _attr_name = ENTITY_NAME_VOICE

    def __init__(self, default_voice: str) -> None:
        """Initialise with the voices of the default voice's language group."""
        self.entity_id = ENTITY_ID_VOICE

        initial_lang = _language_for_voice(default_voice)
        self._voice_codes = _sort_voices(
            VOICES_BY_LANGUAGE.get(initial_lang, [DEFAULT_VOICE])
        )
        self._attr_options = list(self._voice_codes)

        default_label = self._label_for_code(default_voice)
        if default_label is not None:
            self._current_code = default_voice
            self._attr_current_option = default_label
        else:
            self._attr_current_option = self._attr_options[0]
            self._current_code = self._voice_codes[self._attr_current_option]

        # Voice label to re-apply the next time the options list is rebuilt
        # for a language change. Seeded with the configured default so the
        # language entity's startup publish keeps the default selected instead
        # of resetting to the first voice of the language; overridden with the
        # restored label in async_added_to_hass when one exists.
        self._pending_restore_voice: str | None = self._attr_current_option

    def _label_for_code(self, code: str) -> str | None:
        """Return the friendly label currently mapped to a voice code, if any."""
        for label, mapped in self._voice_codes.items():
            if mapped == code:
                return label
        return None

    def _set_random_voice_options(self) -> None:
        """Collapse the dropdown to the single Random Voice option."""
        self._voice_codes = {RANDOM_VOICE_NAME: RANDOM_VOICE_CODE}
        self._attr_options = [RANDOM_VOICE_NAME]
        self._current_code = RANDOM_VOICE_CODE
        self._attr_current_option = RANDOM_VOICE_NAME

    async def async_added_to_hass(self) -> None:
        """Restore the last voice and sync with the published language.

        A restored non-random voice cannot be applied until the options list
        reflects the restored language, so it is stashed in
        _pending_restore_voice and consumed by _apply_language - either right
        here (when the language entity was added first and has already
        published its code) or when SIGNAL_LANGUAGE_CHANGED arrives.
        """
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state:
            if last_state.state == RANDOM_VOICE_NAME:
                # Random voice does not depend on the language's options list.
                self._set_random_voice_options()
                LOGGER.debug("Voice restored to: %s", RANDOM_VOICE_NAME)
            else:
                self._pending_restore_voice = last_state.state
                LOGGER.debug("Voice restore deferred: %s", last_state.state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_LANGUAGE_CHANGED, self._handle_language_changed
            )
        )

        published = self.hass.data.get(DOMAIN, {}).get(HASS_DATA_CURRENT_LANGUAGE)
        if published is not None:
            self._apply_language(published)

    @callback
    def _handle_language_changed(self, new_language_code: str) -> None:
        """Rebuild the options list for a new language and write state."""
        self._apply_language(new_language_code)

    @callback
    def _apply_language(self, new_language_code: str) -> None:
        """Rebuild options for a language, consuming any pending restore.

        Selects the pending restored voice if it exists in the new options
        list, otherwise the first voice of the language.
        """
        if new_language_code == RANDOM_VOICE_CODE:
            self._set_random_voice_options()
            self._pending_restore_voice = None
            self.async_write_ha_state()
            LOGGER.debug("Voice options set to Random Voice")
            return

        raw_codes = (
            ALL_VOICES
            if new_language_code == LANGUAGE_ALL_CODE
            else VOICES_BY_LANGUAGE.get(new_language_code, [DEFAULT_VOICE])
        )
        self._voice_codes = _sort_voices(raw_codes)
        self._attr_options = list(self._voice_codes)

        pending = self._pending_restore_voice
        self._pending_restore_voice = None
        if pending and pending in self._voice_codes:
            self._current_code = self._voice_codes[pending]
            self._attr_current_option = pending
        else:
            self._attr_current_option = self._attr_options[0]
            self._current_code = self._voice_codes[self._attr_current_option]

        self.async_write_ha_state()
        LOGGER.debug(
            "Voice options updated for '%s', selected '%s' (%s)",
            new_language_code,
            self._attr_current_option,
            self._current_code,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw API code for use in button.py and automations."""
        return {"code": self._current_code}

    async def async_select_option(self, option: str) -> None:
        """Handle voice selection - option is a friendly label."""
        if option not in self._voice_codes:
            LOGGER.warning("Voice '%s' not available for current language.", option)
            return
        self._current_code = self._voice_codes[option]
        self._attr_current_option = option
        self.async_write_ha_state()
        LOGGER.debug("Voice changed to: %s (%s)", option, self._current_code)


class DeviceSelectEntity(SelectEntity, RestoreEntity):
    """Shared media player dropdown - one instance for the whole integration.

    Shows HA friendly names (e.g. "Kitchen Speaker") in the dropdown; the raw
    media_player entity_id is exposed via the 'code' state attribute.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_icon = "mdi:speaker"
    _attr_unique_id = UNIQUE_ID_DEVICE
    _attr_name = ENTITY_NAME_DEVICE

    def __init__(self) -> None:
        """Initialise with a placeholder until hass.states is available."""
        self.entity_id = ENTITY_ID_DEVICE
        self._attr_options = [PLACEHOLDER_LOADING]
        self._attr_current_option = PLACEHOLDER_LOADING
        self._device_names: list[str] = []
        self._device_ids: list[str] = []
        self._current_device_id: str = ""

    async def async_added_to_hass(self) -> None:
        """Scan for media players and keep the list updated continuously.

        Three mechanisms keep the device list current:

        1. An initial scan - catches devices already loaded.
        2. A homeassistant_started listener - catches devices loaded after
           this integration but before HA reports fully started.
        3. A filtered state_changed listener - catches devices that register
           late (e.g. browser_mod, mobile app) or flip availability. The
           filter runs in core's event dispatch, so routine attribute ticks
           (volume, position) never reach this entity.

        The previously selected device is restored from the state database.
        """
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes.get("code"):
            self._current_device_id = last_state.attributes["code"]
            LOGGER.debug("Device restored to: %s", self._current_device_id)

        await self._async_refresh_devices()

        @callback
        def _on_started(_event: Event) -> None:
            self.hass.async_create_task(self._async_refresh_devices())

        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
        )

        @callback
        def _usability_flipped(data: EventStateChangedData) -> bool:
            """Pass only media_player events where usability actually changed."""
            if not data["entity_id"].startswith("media_player."):
                return False
            return _usable(data["old_state"]) != _usable(data["new_state"])

        @callback
        def _on_state_changed(_event: Event[EventStateChangedData]) -> None:
            self.hass.async_create_task(self._async_refresh_devices())

        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, _on_state_changed, event_filter=_usability_flipped
            )
        )

    async def _async_refresh_devices(self) -> None:
        """Rebuild the options list from the usable media players in hass.states."""
        all_players = sorted(
            self.hass.states.async_all("media_player"),
            key=lambda s: s.entity_id,
        )
        player_states = [s for s in all_players if _usable(s)]

        if not player_states:
            return

        new_names = [
            s.attributes.get("friendly_name", s.entity_id) for s in player_states
        ]
        new_ids = [s.entity_id for s in player_states]

        # Nothing changed: same players available and the current selection
        # still resolves. Skip the rebuild and state write entirely.
        if (
            new_ids == self._device_ids
            and new_names == self._device_names
            and self._current_device_id in new_ids
        ):
            return

        self._device_names = new_names
        self._device_ids = new_ids
        self._attr_options = self._device_names

        if self._current_device_id in self._device_ids:
            idx = self._device_ids.index(self._current_device_id)
            self._attr_current_option = self._device_names[idx]
        elif not self._current_device_id:
            self._current_device_id = self._device_ids[0]
            self._attr_current_option = self._device_names[0]
        else:
            # The restored device isn't available yet (e.g. browser_mod has
            # not registered). Keep the restored value rather than overwriting
            # with the first device - the state listener will re-run this when
            # it appears.
            return

        self.async_write_ha_state()
        LOGGER.debug(
            "TikTokTTS device list: %d media player(s) found", len(self._device_ids)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw media_player entity_id for use in button.py."""
        return {"code": self._current_device_id}

    async def async_select_option(self, option: str) -> None:
        """Handle device selection - option is a friendly name.

        Matches against the resolved device names, not _attr_options, so the
        startup "(loading...)" placeholder can never be selected into a
        device id (it sits in options while _device_ids is still empty).
        """
        if option not in self._device_names:
            LOGGER.warning(
                "Ignoring selection of '%s' - no matching media player", option
            )
            return
        idx = self._device_names.index(option)
        self._current_device_id = self._device_ids[idx]
        self._attr_current_option = option
        self.async_write_ha_state()
        LOGGER.debug("Output device: %s (%s)", option, self._current_device_id)
