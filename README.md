# TikTok TTS

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

_Integration to use the [reverse engineered TikTok speech API by Weilbyte](https://weilbyte.github.io/tiktok-tts/)._

As @Weilbyte work is based on the following repository, I want to attribute them here as well.

https://github.com/oscie57/tiktok-voice

Visit their page and appreciate their work as well!

**This integration will set up the following platforms.**

Platform | Description
-- | --
`tts` | Generate a audio file based on given input text to play over speakers.

## Installation

There are two methods to install this custom_integration.

### Installation with HACS

As this is a HACS component, you can simply add this repository [philipp-luettecke/tiktoktts](https://github.com/philipp-luettecke/tiktoktts) as custom repository to HACS and afterwards search for the TikTokTTS Integration.
Now you can install it.

1. Add `https://github.com/philipp-luettecke/tiktoktts` to HACS as custom repository
1. Install `TikTokTTS`component
1. Restart Home Assistant
1. Now add `tiktoktts` as platform in your `configuration.yaml`

```yaml
tts:
  - platform: tiktoktts
```


### Manual Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `tiktoktts`.
1. Download _all_ the files from the `custom_components/tiktoktts/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Restart Home Assistant
1. Now add `tiktoktts` as platform in your `configuration.yaml`

```yaml
tts:
  - platform: tiktoktts
```

## How to use

After installing the integration you will be presented with a new Service `tiktoktts_say`.
You can now call this service and add a option `voice` to select one of the voices available in `custom_component/tiktoktts/const.py`.

I'm trying to keep the list equivalent to the voices available on the original [tiktok-voice](https://github.com/oscie57/tiktok-voice) rpositories [Wiki page](https://github.com/oscie57/tiktok-voice/wiki/Voice-Codes).

```yaml
service: tts.tiktoktts_say
data:
  cache: false
  message: Sample Text
  entity_id: media_player.<entity_id>
  options:
    voice: en_us_001
```

<!--1. In the HA UI go to "Configuration" -> "Integrations" click "+" and search for "TikTok TTS

## Configuration is done in the UI

<!--->

## Contributions are welcome!

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)



***

[tiktoktts]: https://github.com/philipp-luettecke/tiktoktts
[buymecoffee]: https://www.buymeacoffee.com/ludeeus
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/philipp-luettecke/tiktoktts.svg?style=for-the-badge
[commits]: https://github.com/philipp-luettecke/tiktoktts/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[discord]: https://discord.gg/Qa5fW2R
[discord-shield]: https://img.shields.io/discord/330944238910963714.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/philipp-luettecke/tiktoktts.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-Philipp%20Luettecke-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/philipp-luettecke/tiktoktts.svg?style=for-the-badge
[releases]: https://github.com/philipp-luettecke/tiktoktts/releases
