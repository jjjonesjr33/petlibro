[![version](https://img.shields.io/github/manifest-json/v/flifloo/ha_petlibro?filename=custom_components%2Fpetlibro%2Fmanifest.json&color=slateblue)](https://github.com/jjjonesjr33/ha_petlibro/releases)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/jjjonesjr33/ha_petlibro)
![GitHub all releases](https://img.shields.io/github/downloads/jjjonesjr33/ha_petlibro/total)
[![Community Forum](https://img.shields.io/static/v1.svg?label=Community&message=Forum&color=41bdf5&logo=HomeAssistant&logoColor=white)](https://community.home-assistant.io/t/petlibro-cloud-integration-non-tuya-wip/759978)

![Logo](https://raw.githubusercontent.com/jjjonesjr33/ha_petlibro/master/docs/media/logo.png)

# PETLIBRO integration for Home Assistant - RFID Feeder/Fountain

Have questions, or need support for one of my configs? Get ahold of me via direct message on discord - `Jamie Jones Jr` / `jjjonesjr33` previously  `JJJonesJr33#0001` 
 
Also if you want to check out all the other things I do follow me on my [**Socials**](https://jjjonesjr33.com/).

## Supported Devices
### This has been reworked to work with the following devices

* One RFID Smart Feeder (PLAF301)
* Dockstream RFID Smart Fountain (PLWF305)

### May or may not work as intended with
* Granary Feeder (PLAF103)

## Features

* This is still a WIP integration, features may or may not be removed at any time. If you have suggestions please let me know.
- Features missing, but in the works.
  > Buttons for scheduling - One RFID Smart Feeder (PLAF301)

  > Buttons to reset Cleaning/Filter Days - Dockstream RFID Smart Fountain (PLWF305)

  > Tracking RFID per pet intance eat/drink - Both (PLAF301) & (PLWF305) - Currently missing the API to setup tracking.

## One RFID Smart Feeder Preview
![One RFID Smart Feeder](https://github.com/jjjonesjr33/ha_petlibro/blob/master/docs/media/Screenshot%202024-10-05%20154145.png)
## Dockstream RFID Smart Fountain Preview
![Dockstream RFID Smart Fountain](https://github.com/jjjonesjr33/ha_petlibro/blob/master/docs/media/Screenshot%202024-10-05%20154229.png)

## Installation

### Manually

Get the folder `custom_components/petlibro` in your HA `config/custom_components`


### Via [HACS](https://hacs.xyz/)
<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=jjjonesjr33&repository=ha_petlibro&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

## Configuration
<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=petlibro" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>

- Enter your credentials.

  > Only one device can be login at the same time.
  >
  > If you to wan to keep your phone connected, create another account for this integration and share your device to it.

# Credit

The following users were the ones who inspired me to add/customize petlibro via a fourm post ~ Thank you!

* ![flifloo](https://github.com/flifloo)
* ![C4-Dimitri](https://github.com/C4-Dimitri)
