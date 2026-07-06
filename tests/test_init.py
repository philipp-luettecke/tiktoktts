"""Tests for the integration lifecycle (__init__.py).

Covers config-entry setup/unload/remove, the shared-singleton ownership
transfer when one of several entries is unloaded, the set_random_voices
service, and persistence of the random-voice pool through the HA Store.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.tiktoktts import _STORAGE_KEY
from custom_components.tiktoktts.const import (
    DOMAIN,
    ENTITY_ID_LANGUAGE,
    ENTITY_ID_TTS_DIRECT,
    ENTITY_ID_TTS_PROXY,
    HASS_DATA_RANDOM_LANGS,
    SERVICE_SET_RANDOM_VOICES,
)

from .helpers import setup_direct, setup_proxy


async def test_unload_last_entry_clears_everything(hass: HomeAssistant) -> None:
    entry = await setup_proxy(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID_TTS_PROXY) is not None
    assert hass.states.get(ENTITY_ID_LANGUAGE) is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    # Last entry gone -> domain data cleared and entities no longer available.
    # (HA keeps registry-backed entities in the state machine as `unavailable`
    # rather than deleting them, so we assert on availability, not absence.)
    assert DOMAIN not in hass.data
    assert hass.states.get(ENTITY_ID_TTS_PROXY).state == STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID_LANGUAGE).state == STATE_UNAVAILABLE


async def test_reload_recreates_entities(hass: HomeAssistant) -> None:
    entry = await setup_proxy(hass)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID_TTS_PROXY) is not None
    assert hass.states.get(ENTITY_ID_LANGUAGE) is not None


async def test_remove_entry(hass: HomeAssistant) -> None:
    entry = await setup_proxy(hass)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None


async def test_two_entries_share_singletons(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    await setup_direct(hass)

    # Both per-entry TTS entities exist; the shared entities exist exactly once.
    assert hass.states.get(ENTITY_ID_TTS_PROXY) is not None
    assert hass.states.get(ENTITY_ID_TTS_DIRECT) is not None
    assert hass.states.get(ENTITY_ID_LANGUAGE) is not None


async def test_unloading_shared_owner_rehomes_to_survivor(hass: HomeAssistant) -> None:
    """Unloading the entry that owns the shared entities re-homes them once.

    The owner stays unloaded (no reload cascade) while exactly one surviving
    entry is reloaded to recreate the shared select/text/button entities.
    """
    proxy = await setup_proxy(hass)  # first entry -> owns shared entities
    direct = await setup_direct(hass)

    assert await hass.config_entries.async_unload(proxy.entry_id)
    await hass.async_block_till_done()

    # The owner stays unloaded - it is NOT ping-ponged back to loaded.
    assert proxy.state is ConfigEntryState.NOT_LOADED
    # The survivor stays loaded and re-homes the shared entities.
    assert direct.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID_TTS_DIRECT).state != STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID_LANGUAGE).state != STATE_UNAVAILABLE
    assert hass.data[DOMAIN].get("shared_owner_entry_id") == direct.entry_id


async def test_unloading_non_owner_leaves_owner_untouched(hass: HomeAssistant) -> None:
    """Unloading a non-owner entry must not disturb the owner or its entities."""
    proxy = await setup_proxy(hass)  # owner
    direct = await setup_direct(hass)  # non-owner

    assert await hass.config_entries.async_unload(direct.entry_id)
    await hass.async_block_till_done()

    # No reload cascade: the owner stays loaded and keeps the shared entities.
    assert direct.state is ConfigEntryState.NOT_LOADED
    assert proxy.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID_TTS_PROXY).state != STATE_UNAVAILABLE
    assert hass.states.get(ENTITY_ID_LANGUAGE).state != STATE_UNAVAILABLE
    assert hass.data[DOMAIN].get("shared_owner_entry_id") == proxy.entry_id


async def test_reloading_owner_with_survivors_keeps_shared_entities(
    hass: HomeAssistant,
) -> None:
    """Reloading the owner (e.g. an options save) must not orphan the shared
    entities or bounce ownership between entries."""
    proxy = await setup_proxy(hass)  # owner
    direct = await setup_direct(hass)

    assert await hass.config_entries.async_reload(proxy.entry_id)
    await hass.async_block_till_done()

    assert proxy.state is ConfigEntryState.LOADED
    assert direct.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID_LANGUAGE).state != STATE_UNAVAILABLE
    assert hass.data[DOMAIN].get("shared_owner_entry_id") in (
        proxy.entry_id,
        direct.entry_id,
    )


# ---------------------------------------------------------------------------
# set_random_voices service + Store persistence
# ---------------------------------------------------------------------------


async def test_service_registered_and_persists_to_store(
    hass: HomeAssistant, hass_storage
) -> None:
    await setup_proxy(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_SET_RANDOM_VOICES)

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_RANDOM_VOICES, {"languages": ["fr", "de"]}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.data[DOMAIN][HASS_DATA_RANDOM_LANGS] == ["fr", "de"]
    assert hass_storage[_STORAGE_KEY]["data"] == {"languages": ["fr", "de"]}


async def test_random_pool_loaded_from_store_on_setup(
    hass: HomeAssistant, hass_storage
) -> None:
    # Pre-seed the store as if a previous run saved a pool (with one bad code).
    hass_storage[_STORAGE_KEY] = {
        "version": 1,
        "data": {"languages": ["de", "not_a_language"]},
    }
    await setup_proxy(hass)
    # Unknown codes are filtered out at load time.
    assert hass.data[DOMAIN][HASS_DATA_RANDOM_LANGS] == ["de"]


async def test_service_survives_after_last_entry_unloaded(
    hass: HomeAssistant, hass_storage
) -> None:
    """The service is registered per HA start, not per entry - calling it
    after the last entry unloads (which clears hass.data[DOMAIN]) must not
    crash, and must still persist to the store."""
    entry = await setup_proxy(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in hass.data

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_RANDOM_VOICES, {"languages": ["ja"]}, blocking=True
    )
    await hass.async_block_till_done()

    assert hass.data[DOMAIN][HASS_DATA_RANDOM_LANGS] == ["ja"]
    assert hass_storage[_STORAGE_KEY]["data"] == {"languages": ["ja"]}
