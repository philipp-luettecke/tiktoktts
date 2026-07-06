"""JavaScript module registration for the TikTok TTS Lovelace card.

This module handles automatic registration of the custom Lovelace card so
users do not need to manually add a resource entry in their dashboard settings.

How it works
------------
1. The www/ folder is registered as a static HTTP path so HA serves the JS
   file at /<domain>/tiktoktts-card.js.

2. The card URL is registered with the frontend via
   ``frontend.add_extra_js_url`` - a helper explicitly provided for custom
   integrations to load an extra JS module. This works in both storage and
   YAML dashboard modes and does not depend on any private Lovelace internals,
   so it is robust across HA core updates. The trade-off is that the module
   loads on every frontend page (negligible for a small card) and does not
   appear in Settings -> Dashboards -> Resources.

3. Registration happens in async_setup (not async_setup_entry) so it runs
   exactly once per HA startup regardless of how many config entries exist.
   There is nothing to wait for - the frontend reads the module list per page
   render - so no deferral is needed.

4. The card URL includes a ?v=<version> query string so the browser cache is
   busted automatically on each integration version bump. The in-memory module
   list is rebuilt every HA start, so each run registers the current version.

5. async_unregister() removes the module URL when the last config entry is
   permanently deleted. It is called from async_remove_entry in __init__.py
   (not async_unload_entry, which also fires on reload/disable).

Note on imports
---------------
This subpackage does NOT import from the parent const.py. Doing so causes
a ModuleNotFoundError during HA's custom integration loading because Python
resolves relative imports differently for subpackages inside custom_components.
Instead, the domain string and logger are defined locally here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.frontend import (
    DATA_EXTRA_MODULE_URL,
    add_extra_js_url,
    remove_extra_js_url,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Domain and card filename defined locally to avoid relative import issues
_DOMAIN = "tiktoktts"
_CARD_FILENAME = "tiktoktts-card.js"
_URL_BASE = f"/{_DOMAIN}"


def _read_version() -> str:
    """Read the integration version from manifest.json.

    Called lazily inside async_register via hass.async_add_executor_job so
    the blocking file I/O does not run on the event loop at import time.
    Falls back to "0.0.0" if the manifest cannot be parsed.
    """
    try:
        manifest = json.loads(
            (Path(__file__).parent.parent / "manifest.json").read_text()
        )
        return manifest.get("version", "0.0.0")
    except Exception:  # noqa: BLE001
        return "0.0.0"


class JSModuleRegistration:
    """Registers the TikTokTTS Lovelace card in Home Assistant.

    Serves the JS file via a static HTTP path and registers the card module
    with the frontend so it is loaded automatically without any manual
    dashboard-resource configuration.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise with the HomeAssistant instance."""
        self.hass = hass
        self._version = "0.0.0"

    async def async_register(self) -> None:
        """Register the static path and the card module URL."""
        self._version = await self.hass.async_add_executor_job(_read_version)
        await self._async_register_path()
        self._register_module_url()

    async def async_unregister(self) -> None:
        """Remove the card module URL (on permanent integration removal)."""
        self._version = await self.hass.async_add_executor_job(_read_version)
        self._unregister_module_url()

    def _module_url(self) -> str:
        """Return the cache-busted module URL for the card."""
        return f"{_URL_BASE}/{_CARD_FILENAME}?v={self._version}"

    async def _async_register_path(self) -> None:
        """Register the www/ folder as a static HTTP path.

        Serves all files in custom_components/tiktoktts/www/ at /<domain>/.
        Catches RuntimeError silently - it means the path is already
        registered (e.g. after a config entry reload).
        """
        # cache_headers stays enabled: the card URL carries a ?v=<version>
        # cache-buster, so browsers can cache aggressively without ever
        # serving a stale card after an upgrade.
        www_path = Path(__file__).parent.parent / "www"
        try:
            await self.hass.http.async_register_static_paths(
                [StaticPathConfig(_URL_BASE, str(www_path))]
            )
            _LOGGER.debug(
                "TikTokTTS: static path registered: %s -> %s", _URL_BASE, www_path
            )
        except RuntimeError:
            _LOGGER.debug("TikTokTTS: static path already registered: %s", _URL_BASE)

    def _register_module_url(self) -> None:
        """Add the card to the frontend's extra-module list (idempotent)."""
        manager = self.hass.data.get(DATA_EXTRA_MODULE_URL)
        if manager is None:
            _LOGGER.debug("TikTokTTS: frontend not ready; skipping card registration")
            return
        url = self._module_url()
        if url not in manager.urls:
            add_extra_js_url(self.hass, url)
            _LOGGER.info("TikTokTTS: Lovelace card registered (%s)", url)

    def _unregister_module_url(self) -> None:
        """Remove the card from the frontend's extra-module list, if present."""
        manager = self.hass.data.get(DATA_EXTRA_MODULE_URL)
        url = self._module_url()
        if manager is not None and url in manager.urls:
            remove_extra_js_url(self.hass, url)
            _LOGGER.debug("TikTokTTS: Lovelace card module removed")
