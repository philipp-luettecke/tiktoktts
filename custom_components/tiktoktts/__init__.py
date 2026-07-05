"""TikTok TTS - Home Assistant Custom Integration.

Entry point for the integration. See README.md for the architecture overview,
per-file responsibilities, and user-facing documentation.

Platform layout: the TTS platform is per config entry (one entity per proxy /
direct entry). The select, text, and button platforms are shared singletons -
forwarded by exactly one entry at a time (the "owner", tracked in
hass.data[DOMAIN][HASS_DATA_SHARED_OWNER]). When the owner is unloaded while
other entries remain, shared.py reloads a survivor so the entities are
re-created under an enabled entry.

Storage convention: all settings live in entry.data (not entry.options), so
config_flow.py and tts.py share a single source of truth. The options flow
writes via async_update_entry(), and the update listener below reloads the
entry so changes take effect immediately.

Credits
-------
Original integration: Philipp Lüttecke (https://github.com/philipp-luettecke/tiktoktts)
Community TTS proxy:  Weilbyte (https://github.com/Weilbyte/tiktok-tts)
Fork author:          Steven Fox / sfox38 (https://github.com/sfox38/tiktoktts)
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    DOMAIN,
    HASS_DATA_CURRENT_LANGUAGE,
    HASS_DATA_RANDOM_LANGS,
    HASS_DATA_RANDOM_STORE,
    HASS_DATA_SHARED_OWNER,
    LOGGER,
    SERVICE_SET_RANDOM_VOICES,
    SIGNAL_RANDOM_POOL_UPDATED,
    SUPPORTED_LANGUAGES,
)
from .frontend import JSModuleRegistration
from .shared import async_schedule_rehome

PLATFORMS: list[Platform] = [
    Platform.TTS,
    Platform.SELECT,
    Platform.TEXT,
    Platform.BUTTON,
]

# TTS is set up for every config entry; the shared platforms are forwarded
# only by the owning entry (see module docstring).
TTS_PLATFORMS: list[Platform] = [Platform.TTS]
SHARED_PLATFORMS: list[Platform] = [Platform.SELECT, Platform.TEXT, Platform.BUTTON]

_STORAGE_KEY = f"{DOMAIN}_random_voices"
_STORAGE_VERSION = 1

# This integration is configured only via the UI config flow; it has no YAML
# configuration. Declaring this satisfies hassfest's requirement that an
# integration implementing async_setup defines a config schema.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def _async_load_random_langs(hass: HomeAssistant) -> None:
    """Load the persisted random-voice language pool into hass.data.

    Creates the Store on first use and filters out any language codes that
    are no longer supported.
    """
    data = hass.data.setdefault(DOMAIN, {})
    store: Store = data.get(HASS_DATA_RANDOM_STORE) or Store(
        hass, _STORAGE_VERSION, _STORAGE_KEY
    )
    data[HASS_DATA_RANDOM_STORE] = store

    saved = await store.async_load()
    if saved and isinstance(saved.get("languages"), list):
        langs = [lang for lang in saved["languages"] if lang in SUPPORTED_LANGUAGES]
    else:
        langs = []
    data[HASS_DATA_RANDOM_LANGS] = langs
    LOGGER.debug("Random voice languages loaded: %s", langs)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the set_random_voices service and the Lovelace card module.

    Runs exactly once per HA startup regardless of how many config entries
    exist, which is why the service and card registration live here rather
    than in async_setup_entry.
    """
    await _async_load_random_langs(hass)

    async def _handle_set_random_voices(call: ServiceCall) -> None:
        languages = call.data.get("languages", [])
        valid = [lang for lang in languages if lang in SUPPORTED_LANGUAGES]
        invalid = [lang for lang in languages if lang not in SUPPORTED_LANGUAGES]
        if invalid:
            LOGGER.warning(
                "Rejected unknown language codes from set_random_voices: %s", invalid
            )
        # setdefault: the service outlives config entries, so this must not
        # assume hass.data[DOMAIN] still exists after the last entry unloads.
        data = hass.data.setdefault(DOMAIN, {})
        data[HASS_DATA_RANDOM_LANGS] = valid
        store: Store = data.get(HASS_DATA_RANDOM_STORE) or Store(
            hass, _STORAGE_VERSION, _STORAGE_KEY
        )
        data[HASS_DATA_RANDOM_STORE] = store
        await store.async_save({"languages": valid})
        LOGGER.debug("Random voice languages saved: %s", valid)
        async_dispatcher_send(hass, SIGNAL_RANDOM_POOL_UPDATED)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_RANDOM_VOICES,
        _handle_set_random_voices,
        schema=vol.Schema(
            {
                vol.Required("languages"): vol.All(cv.ensure_list, [cv.string]),
            }
        ),
    )

    # frontend.add_extra_js_url adds the card to the frontend's module list,
    # which is read per page render - nothing to wait for, no deferral needed.
    await JSModuleRegistration(hass).async_register()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TikTok TTS from a config entry.

    Every entry sets up its own TTS platform. The shared platforms (select,
    text, button) are forwarded only when no other entry currently owns them,
    so the shared entities exist exactly once no matter how many entries load.
    """
    data = hass.data.setdefault(DOMAIN, {})

    # Re-populate the random-voice pool if hass.data[DOMAIN] was cleared by a
    # previous last-entry unload (async_setup only runs once per HA startup).
    if HASS_DATA_RANDOM_LANGS not in data:
        await _async_load_random_langs(hass)

    LOGGER.debug("TikTokTTS setup_entry: entry=%s", entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, TTS_PLATFORMS)

    if data.get(HASS_DATA_SHARED_OWNER) is None:
        data[HASS_DATA_SHARED_OWNER] = entry.entry_id
        await hass.config_entries.async_forward_entry_setups(entry, SHARED_PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Called by HA when the user removes or disables the integration, or just
    before a reload. The owner tears down all platforms; other entries only
    tear down their TTS platform. When entries remain after the owner leaves,
    ownership is released and shared.py re-homes the entities to a survivor.
    """
    data = hass.data.get(DOMAIN, {})
    is_owner = data.get(HASS_DATA_SHARED_OWNER) == entry.entry_id

    platforms = PLATFORMS if is_owner else TTS_PLATFORMS
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if not unload_ok:
        return False

    if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
        LOGGER.debug("Last TikTokTTS config entry unloaded - clearing all data")
        hass.data.pop(DOMAIN, None)
        return True

    if is_owner:
        data.pop(HASS_DATA_SHARED_OWNER, None)
        data.pop(HASS_DATA_CURRENT_LANGUAGE, None)
        async_schedule_rehome(hass)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up when a config entry is permanently deleted.

    Called by HA only on true removal (not on reload or disable), which makes
    it the right place to unregister the Lovelace card module.
    """
    if not hass.config_entries.async_entries(DOMAIN):
        LOGGER.debug("Last TikTokTTS entry removed - unregistering Lovelace card")
        await JSModuleRegistration(hass).async_unregister()


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its data is updated (end of the options flow)."""
    LOGGER.debug("Config entry updated for %s - reloading", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)
