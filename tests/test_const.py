"""Data-integrity tests for const.py.

These guard the static voice/language tables against editing mistakes: a
typo'd voice code, a language present in one table but not another, or a
default that points at a non-existent voice would all break the integration
at runtime. None of these need Home Assistant.
"""

from __future__ import annotations

import collections

from custom_components.tiktoktts import const


def test_supported_languages_matches_voice_table() -> None:
    """SUPPORTED_LANGUAGES is derived from the voice table keys, in order."""
    assert const.SUPPORTED_LANGUAGES == list(const.VOICES_BY_LANGUAGE.keys())


def test_all_voices_is_flattened_voice_table() -> None:
    """ALL_VOICES is exactly every voice across every language group."""
    expected = [v for voices in const.VOICES_BY_LANGUAGE.values() for v in voices]
    assert const.ALL_VOICES == expected


def test_no_duplicate_voice_codes() -> None:
    """No voice code appears in more than one language group."""
    dupes = [code for code, n in collections.Counter(const.ALL_VOICES).items() if n > 1]
    assert dupes == []


def test_every_language_has_at_least_one_voice() -> None:
    """An empty voice list would make a language unusable."""
    for lang, voices in const.VOICES_BY_LANGUAGE.items():
        assert voices, f"language {lang} has no voices"


def test_default_voice_and_language_are_consistent() -> None:
    """The default voice exists and belongs to the default language."""
    assert const.DEFAULT_VOICE in const.ALL_VOICES
    assert const.DEFAULT_LANG in const.SUPPORTED_LANGUAGES
    assert const.DEFAULT_VOICE in const.VOICES_BY_LANGUAGE[const.DEFAULT_LANG]


def test_voice_names_keys_are_real_voices() -> None:
    """Every friendly-name mapping points at a voice that actually exists."""
    unknown = set(const.VOICE_NAMES) - set(const.ALL_VOICES)
    assert unknown == set(), f"VOICE_NAMES has unknown codes: {unknown}"


def test_language_names_cover_exactly_supported_languages() -> None:
    """Friendly language names exist for every language and no extras."""
    assert set(const.LANGUAGE_NAMES) == set(const.SUPPORTED_LANGUAGES)


def test_direct_endpoints_are_unique_https_urls() -> None:
    """Fallback endpoints must be distinct https URLs."""
    assert const.DIRECT_API_ENDPOINTS, "no direct endpoints configured"
    assert len(const.DIRECT_API_ENDPOINTS) == len(set(const.DIRECT_API_ENDPOINTS))
    assert all(ep.startswith("https://") for ep in const.DIRECT_API_ENDPOINTS)


def test_default_proxy_endpoint_is_https() -> None:
    assert const.DEFAULT_PROXY_ENDPOINT.startswith("https://")


def test_entity_id_constants_follow_naming_scheme() -> None:
    """Entity-id constants are derived from the domain and stay stable."""
    assert const.ENTITY_ID_TTS_PROXY == "tts.tiktoktts_proxy"
    assert const.ENTITY_ID_TTS_DIRECT == "tts.tiktoktts_direct"
    assert const.ENTITY_ID_LANGUAGE == "select.tiktoktts_language"
    assert const.ENTITY_ID_VOICE == "select.tiktoktts_voice"
    assert const.ENTITY_ID_DEVICE == "select.tiktoktts_device"
    assert const.ENTITY_ID_MESSAGE == "text.tiktoktts_message"
    assert const.ENTITY_ID_SPEAK == "button.tiktoktts_speak"


def test_request_tuning_values_are_sane() -> None:
    """Retry/timeout knobs are within sensible bounds."""
    assert const.REQUEST_MAX_RETRIES >= 0
    assert const.REQUEST_TIMEOUT > 0
    assert const.REQUEST_RETRY_DELAY >= 0
    assert const.FALLBACK_MAX_RETRIES >= 0
    assert const.FALLBACK_TIMEOUT > 0
    assert const.DIRECT_API_CHUNK_SIZE > 0


def test_status_codes_distinct() -> None:
    """OK and invalid-session status codes must differ."""
    assert const.DIRECT_API_STATUS_OK != const.DIRECT_API_STATUS_INVALID_SESSION
