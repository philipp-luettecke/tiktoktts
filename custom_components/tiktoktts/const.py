"""Constants for tiktoktts."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "TikTok TTS"
DOMAIN = "tiktoktts"
ATTRIBUTION = "Using API from https://github.com/Weilbyte/tiktok-tts"
UUID = "tiktoktts-uuid"

CONF_ENDPOINT = "api_endpoint"
CONF_VOICE = "voice"

DEFAULT_ENDPOINT = "https://tiktok-tts.weilnet.workers.dev"
DEFAULT_VOICE = "de_001"
DEFAULT_LANG = "de"

# available voices taken over from
# https://raw.githubusercontent.com/oscie57/tiktok-voice/main/main.py

SUPPORTED_VOICES = [
    # DISNEY VOICES
    "en_us_ghostface",  # Ghost Face
    "en_us_chewbacca",  # Chewbacca
    "en_us_c3po",  # C3PO
    "en_us_stitch",  # Stitch
    "en_us_stormtrooper",  # Stormtrooper
    "en_us_rocket",  # Rocket
    # ENGLISH VOICES
    "en_au_001",  # English AU - Female
    "en_au_002",  # English AU - Male
    "en_uk_001",  # English UK - Male 1
    "en_uk_003",  # English UK - Male 2
    "en_us_001",  # English US - Female (Int. 1)
    "en_us_002",  # English US - Female (Int. 2)
    "en_us_006",  # English US - Male 1
    "en_us_007",  # English US - Male 2
    "en_us_009",  # English US - Male 3
    "en_us_010",  # English US - Male 4
    # EUROPE VOICES
    "fr_001",  # French - Male 1
    "fr_002",  # French - Male 2
    "de_001",  # German - Female
    "de_002",  # German - Male
    "es_002",  # Spanish - Male
    # AMERICA VOICES
    "es_mx_002",  # Spanish MX - Male
    "br_001",  # Portuguese BR - Female 1
    "br_003",  # Portuguese BR - Female 2
    "br_004",  # Portuguese BR - Female 3
    "br_005",  # Portuguese BR - Male
    # ASIA VOICES
    "id_001",  # Indonesian - Female
    "jp_001",  # Japanese - Female 1
    "jp_003",  # Japanese - Female 2
    "jp_005",  # Japanese - Female 3
    "jp_006",  # Japanese - Male
    "kr_002",  # Korean - Male 1
    "kr_003",  # Korean - Female
    "kr_004",  # Korean - Male 2
    # SINGING VOICES
    "en_female_f08_salut_damour"  # Alto
    "en_male_m03_lobby"  # Tenor
    "en_female_f08_warmy_breeze"  # Warmy Breeze
    "en_male_m03_sunshine_soon"  # Sunshine Soon
    # OTHER
    "en_male_narration"  # narrator
    "en_male_funny"  # wacky
    "en_female_emotional",  # peaceful
]


SUPPORTED_LANGUAGES = ["en", "fr", "de", "es", "pt", "id", "jpn", "ko"]

DEFAULT_VOICES = {
    "en":"en_us_001",
    "fr":"fr_001",
    "de":"de_001",
    "es":"es_001",
    "pt":"br_001",
    "id":"id_001",
    "jpn":"jp_001",
    "ko":"kr_002"}

SUPPORTED_OPTIONS = [CONF_VOICE]
