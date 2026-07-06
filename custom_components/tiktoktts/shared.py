"""Re-homing of the shared singleton entities between config entries.

The select / text / button platforms are forwarded by exactly one config
entry at a time - the "owner", recorded in hass.data[DOMAIN] under
HASS_DATA_SHARED_OWNER. When the owner is unloaded while other entries
remain, the shared entities would be left registered under a disabled
config entry (and could not be re-enabled), so a surviving entry must be
reloaded to claim ownership and recreate them under itself.

The reload cannot run inside the owner's unload, so it is deferred to a
tracked hass task that checks, once the unload has fully completed, whether
ownership is still unclaimed. This makes the deferral safe against the two
races the old call_soon hook was exposed to: a same-entry reload (the entry
reclaims ownership in its own setup before the task looks) and HA shutdown
(no task is scheduled while hass is stopping).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, HASS_DATA_SHARED_OWNER, LOGGER


@callback
def async_schedule_rehome(hass: HomeAssistant) -> None:
    """Schedule a re-home check after the current unload completes."""
    if hass.is_stopping:
        return
    hass.async_create_task(
        _async_rehome_to_survivor(hass),
        name=f"{DOMAIN} re-home shared entities",
        eager_start=False,
    )


async def _async_rehome_to_survivor(hass: HomeAssistant) -> None:
    """Reload one loaded survivor so it recreates the shared entities.

    A no-op when ownership has already been re-claimed (the owner was merely
    reloaded, e.g. after an options save) or when the integration has been
    torn down entirely.
    """
    data = hass.data.get(DOMAIN)
    if data is None or data.get(HASS_DATA_SHARED_OWNER) is not None:
        return
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            LOGGER.debug(
                "Re-homing shared entities to surviving entry %s", entry.entry_id
            )
            await hass.config_entries.async_reload(entry.entry_id)
            return
