"""Tests for the Lovelace card registration (frontend/__init__.py).

The card is registered with the frontend via ``add_extra_js_url`` rather than
the private Lovelace resources collection, so the tests assert on the frontend's
extra-module URL manager (seeded directly so no full frontend setup is needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager
from homeassistant.core import HomeAssistant

from custom_components.tiktoktts.frontend import JSModuleRegistration, _read_version

# Derived from the manifest so a version bump never breaks these tests.
MANIFEST_VERSION = json.loads(
    (
        Path(__file__).parent.parent
        / "custom_components"
        / "tiktoktts"
        / "manifest.json"
    ).read_text()
)["version"]
CARD_URL = f"/tiktoktts/tiktoktts-card.js?v={MANIFEST_VERSION}"


def _seed_module_manager(hass: HomeAssistant) -> UrlManager:
    """Install a real (empty) extra-module URL manager, as frontend setup would."""
    manager = UrlManager(lambda *args: None, [])
    hass.data[DATA_EXTRA_MODULE_URL] = manager
    return manager


def _registration(
    hass: HomeAssistant, version: str = MANIFEST_VERSION
) -> JSModuleRegistration:
    reg = JSModuleRegistration(hass)
    reg._version = version
    return reg


def test_read_version_returns_manifest_version() -> None:
    assert _read_version() == MANIFEST_VERSION


def test_read_version_falls_back_when_manifest_unreadable() -> None:
    with patch(
        "custom_components.tiktoktts.frontend.Path.read_text",
        side_effect=OSError("boom"),
    ):
        assert _read_version() == "0.0.0"


async def test_registers_card_module_url(hass: HomeAssistant) -> None:
    manager = _seed_module_manager(hass)
    _registration(hass)._register_module_url()
    assert CARD_URL in manager.urls


async def test_register_is_idempotent(hass: HomeAssistant) -> None:
    manager = _seed_module_manager(hass)
    reg = _registration(hass)
    reg._register_module_url()
    reg._register_module_url()
    # The same URL is registered only once, never duplicated.
    assert list(manager.urls).count(CARD_URL) == 1


async def test_register_without_frontend_is_noop(hass: HomeAssistant) -> None:
    # No extra-module manager in hass.data -> must not raise.
    assert DATA_EXTRA_MODULE_URL not in hass.data
    _registration(hass)._register_module_url()


async def test_unregister_removes_card(hass: HomeAssistant) -> None:
    manager = _seed_module_manager(hass)
    reg = _registration(hass)
    reg._register_module_url()
    assert CARD_URL in manager.urls

    reg._unregister_module_url()
    assert CARD_URL not in manager.urls


async def test_unregister_without_frontend_is_noop(hass: HomeAssistant) -> None:
    # No extra-module manager in hass.data -> must return cleanly without raising.
    _registration(hass)._unregister_module_url()


def test_module_url_includes_version(hass: HomeAssistant) -> None:
    assert (
        _registration(hass, "9.9.9")._module_url()
        == "/tiktoktts/tiktoktts-card.js?v=9.9.9"
    )
