"""Tests for the language / voice / device select entities (select.py).

Pure label<->code helpers are tested directly; the dropdown wiring (language
change rebuilds the voice list, the random-voice option, device discovery) is
tested through a fully set-up config entry and the `select.select_option`
service.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.tiktoktts.const import (
    ALL_VOICES,
    ENTITY_ID_DEVICE,
    ENTITY_ID_LANGUAGE,
    ENTITY_ID_VOICE,
    LANGUAGE_ALL_CODE,
    LANGUAGE_ALL_NAME,
    PLACEHOLDER_LOADING,
    RANDOM_VOICE_CODE,
    RANDOM_VOICE_LANG_NAME,
    RANDOM_VOICE_NAME,
    SUPPORTED_LANGUAGES,
)
from custom_components.tiktoktts.select import (
    _lang_to_name,
    _name_to_lang,
    _sort_voices,
    _voice_to_name,
)

from .helpers import setup_proxy


async def _select(hass: HomeAssistant, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": option},
        blocking=True,
    )


# ---------------------------------------------------------------------------
# Pure label/code helpers
# ---------------------------------------------------------------------------


def test_lang_name_round_trip() -> None:
    for code in SUPPORTED_LANGUAGES:
        assert _name_to_lang(_lang_to_name(code)) == code


def test_lang_special_codes() -> None:
    assert _lang_to_name(LANGUAGE_ALL_CODE) == LANGUAGE_ALL_NAME
    assert _lang_to_name(RANDOM_VOICE_CODE) == RANDOM_VOICE_LANG_NAME
    assert _name_to_lang(LANGUAGE_ALL_NAME) == LANGUAGE_ALL_CODE
    assert _name_to_lang(RANDOM_VOICE_LANG_NAME) == RANDOM_VOICE_CODE


def test_lang_name_unknown_passthrough() -> None:
    assert _lang_to_name("xx") == "xx"
    assert _name_to_lang("not a language") == "not a language"


def test_voice_to_name_known_and_unknown() -> None:
    assert _voice_to_name("en_male_narration") == "Story Teller"
    assert _voice_to_name("totally_unknown") == "totally_unknown"


def test_sort_voices_orders_by_friendly_name() -> None:
    # Returns an ordered {label: code} map sorted by friendly name.
    mapping = _sort_voices(["en_us_007", "en_us_001"])  # Professor, Jessie
    assert list(mapping) == ["Jessie", "Professor"]
    assert mapping == {"Jessie": "en_us_001", "Professor": "en_us_007"}


# ---------------------------------------------------------------------------
# Language / voice dropdown integration
# ---------------------------------------------------------------------------


async def test_initial_language_and_voice_from_default(hass: HomeAssistant) -> None:
    """The configured default voice (and its language) survive a fresh boot."""
    await setup_proxy(hass)  # default voice en_us_001 -> language en_us

    assert hass.states.get(ENTITY_ID_LANGUAGE).attributes["code"] == "en_us"

    # The configured default voice must be preserved through the language
    # entity's startup notify - not reset to the first voice of the language.
    voice = hass.states.get(ENTITY_ID_VOICE)
    assert voice.attributes["code"] == "en_us_001"
    assert voice.state == "Jessie"


async def test_initial_voice_honours_non_default_config(hass: HomeAssistant) -> None:
    """A different configured default voice is preserved on a fresh boot too."""
    await setup_proxy(hass, voice="en_us_007")
    assert hass.states.get(ENTITY_ID_VOICE).attributes["code"] == "en_us_007"
    assert hass.states.get(ENTITY_ID_VOICE).state == "Professor"


async def test_restored_voice_is_preserved(hass: HomeAssistant) -> None:
    """A voice persisted across restart is re-applied against its language."""
    mock_restore_cache(
        hass,
        (
            State(ENTITY_ID_LANGUAGE, "🇺🇸 English (US)"),
            State(ENTITY_ID_VOICE, "Professor"),  # en_us_007
        ),
    )
    await setup_proxy(hass)

    assert hass.states.get(ENTITY_ID_LANGUAGE).attributes["code"] == "en_us"
    assert hass.states.get(ENTITY_ID_VOICE).attributes["code"] == "en_us_007"


async def test_changing_language_rebuilds_voice_list(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    await _select(hass, ENTITY_ID_LANGUAGE, "🇫🇷 French")

    assert hass.states.get(ENTITY_ID_LANGUAGE).attributes["code"] == "fr"
    voice = hass.states.get(ENTITY_ID_VOICE)
    # First French voice by friendly-name order.
    assert voice.attributes["code"] == "fr_001"
    assert set(voice.attributes["options"]) == {"French - Male 1", "French - Male 2"}


async def test_all_languages_shows_every_voice(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    await _select(hass, ENTITY_ID_LANGUAGE, LANGUAGE_ALL_NAME)
    voice = hass.states.get(ENTITY_ID_VOICE)
    assert len(voice.attributes["options"]) == len(ALL_VOICES)


async def test_selecting_a_voice_updates_code(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    await _select(hass, ENTITY_ID_VOICE, "Professor")  # en_us_007
    assert hass.states.get(ENTITY_ID_VOICE).attributes["code"] == "en_us_007"


async def test_unknown_option_is_rejected_by_service(hass: HomeAssistant) -> None:
    """HA validates the option list, so a bad option never reaches the entity."""
    await setup_proxy(hass)
    before = hass.states.get(ENTITY_ID_VOICE).attributes["code"]
    with pytest.raises(HomeAssistantError):
        await _select(hass, ENTITY_ID_VOICE, "Nonexistent Voice")
    assert hass.states.get(ENTITY_ID_VOICE).attributes["code"] == before


# ---------------------------------------------------------------------------
# Random-voice option
# ---------------------------------------------------------------------------


async def test_random_voice_option_appears_after_service(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    # Random option absent until a pool is configured.
    assert (
        RANDOM_VOICE_LANG_NAME
        not in hass.states.get(ENTITY_ID_LANGUAGE).attributes["options"]
    )

    await hass.services.async_call(
        "tiktoktts", "set_random_voices", {"languages": ["fr", "de"]}, blocking=True
    )
    await hass.async_block_till_done()

    lang = hass.states.get(ENTITY_ID_LANGUAGE)
    assert RANDOM_VOICE_LANG_NAME in lang.attributes["options"]
    assert lang.attributes["random_voice_languages"] == ["fr", "de"]

    await _select(hass, ENTITY_ID_LANGUAGE, RANDOM_VOICE_LANG_NAME)
    voice = hass.states.get(ENTITY_ID_VOICE)
    assert voice.attributes["code"] == RANDOM_VOICE_CODE
    assert voice.state == RANDOM_VOICE_NAME


async def test_set_random_voices_rejects_unknown_codes(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    await hass.services.async_call(
        "tiktoktts", "set_random_voices", {"languages": ["fr", "bogus"]}, blocking=True
    )
    await hass.async_block_till_done()
    # Only the valid language survives.
    assert hass.states.get(ENTITY_ID_LANGUAGE).attributes["random_voice_languages"] == [
        "fr"
    ]


async def test_set_random_voices_accepts_every_supported_language(
    hass: HomeAssistant,
) -> None:
    """Every code in SUPPORTED_LANGUAGES (incl. disney) must be accepted.

    Guards against the dashboard card sending a friendly label instead of the
    API code - the class of bug behind the old Disney emoji mismatch.
    """
    await setup_proxy(hass)
    await hass.services.async_call(
        "tiktoktts",
        "set_random_voices",
        {"languages": list(SUPPORTED_LANGUAGES)},
        blocking=True,
    )
    await hass.async_block_till_done()
    saved = hass.states.get(ENTITY_ID_LANGUAGE).attributes["random_voice_languages"]
    assert saved == list(SUPPORTED_LANGUAGES)


async def test_language_options_attribute_maps_codes_to_names(
    hass: HomeAssistant,
) -> None:
    """The card builds its checkbox list from language_options (code+name pairs)."""
    await setup_proxy(hass)
    options = hass.states.get(ENTITY_ID_LANGUAGE).attributes["language_options"]
    by_code = {o["code"]: o["name"] for o in options}
    # Every supported language is present, keyed by API code (not friendly label).
    assert set(by_code) == set(SUPPORTED_LANGUAGES)
    assert by_code["disney"] == "🎭 Disney / Character"


# ---------------------------------------------------------------------------
# Device select
# ---------------------------------------------------------------------------


async def test_device_select_discovers_media_players(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "media_player.kitchen", "idle", {"friendly_name": "Kitchen Speaker"}
    )
    hass.states.async_set(
        "media_player.broken", "unavailable", {"friendly_name": "Broken"}
    )
    await setup_proxy(hass)

    device = hass.states.get(ENTITY_ID_DEVICE)
    # The unavailable player is filtered out.
    assert device.attributes["options"] == ["Kitchen Speaker"]
    assert device.attributes["code"] == "media_player.kitchen"


async def test_device_select_late_registration(hass: HomeAssistant) -> None:
    await setup_proxy(hass)
    # A media_player that appears after setup is picked up by the listener.
    hass.states.async_set("media_player.den", "playing", {"friendly_name": "Den"})
    await hass.async_block_till_done()

    device = hass.states.get(ENTITY_ID_DEVICE)
    assert "Den" in device.attributes["options"]
    assert device.attributes["code"] == "media_player.den"


async def test_device_selection_switches_device(hass: HomeAssistant) -> None:
    hass.states.async_set("media_player.kitchen", "idle", {"friendly_name": "Kitchen"})
    hass.states.async_set("media_player.den", "idle", {"friendly_name": "Den"})
    await setup_proxy(hass)

    await _select(hass, ENTITY_ID_DEVICE, "Kitchen")
    assert (
        hass.states.get(ENTITY_ID_DEVICE).attributes["code"] == "media_player.kitchen"
    )

    await _select(hass, ENTITY_ID_DEVICE, "Den")
    assert hass.states.get(ENTITY_ID_DEVICE).attributes["code"] == "media_player.den"


async def test_device_placeholder_selection_is_ignored(hass: HomeAssistant) -> None:
    """Selecting the '(loading...)' placeholder must not crash the service.

    With no usable media players, the placeholder is the only option, so HA's
    own option validation lets it through - the entity has to reject it.
    """
    await setup_proxy(hass)  # no media players exist

    device = hass.states.get(ENTITY_ID_DEVICE)
    assert device.attributes["options"] == [PLACEHOLDER_LOADING]

    await _select(hass, ENTITY_ID_DEVICE, PLACEHOLDER_LOADING)

    device = hass.states.get(ENTITY_ID_DEVICE)
    assert device.state == PLACEHOLDER_LOADING
    assert device.attributes["code"] == ""


async def test_device_restored_selection_waits_for_late_player(
    hass: HomeAssistant,
) -> None:
    """A restored device that is not yet available is kept, not overwritten."""
    mock_restore_cache(
        hass,
        (State(ENTITY_ID_DEVICE, "Den", {"code": "media_player.den"}),),
    )
    hass.states.async_set("media_player.kitchen", "idle", {"friendly_name": "Kitchen"})
    await setup_proxy(hass)

    # Kitchen is available but must NOT displace the restored (absent) Den.
    assert hass.states.get(ENTITY_ID_DEVICE).attributes["code"] == "media_player.den"

    # When Den registers, the listener resolves the restored selection.
    hass.states.async_set("media_player.den", "idle", {"friendly_name": "Den"})
    await hass.async_block_till_done()

    device = hass.states.get(ENTITY_ID_DEVICE)
    assert device.state == "Den"
    assert device.attributes["code"] == "media_player.den"
