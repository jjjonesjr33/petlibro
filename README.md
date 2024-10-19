[![version](https://img.shields.io/github/manifest-json/v/jjjonesjr33/petlibro?filename=custom_components%2Fpetlibro%2Fmanifest.json&color=slateblue)](https://github.com/jjjonesjr33/petlibro/releases)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/jjjonesjr33/petlibro)
![GitHub all releases](https://img.shields.io/github/downloads/jjjonesjr33/petlibro/total)
[![Community Forum](https://img.shields.io/static/v1.svg?label=Community&message=Forum&color=41bdf5&logo=HomeAssistant&logoColor=white)](https://community.home-assistant.io/t/petlibro-cloud-integration-non-tuya-wip/759978)

![Logo](https://raw.githubusercontent.com/jjjonesjr33/ha_petlibro/master/docs/media/logo.png)

# PETLIBRO integration for Home Assistant

## Have questions, or need support?
Get ahold of me via direct message on discord - `Jamie Jones Jr` / `jjjonesjr33` previously  `JJJonesJr33#0001` 
 
Also if you want to check out all the other things I do follow me on my [**Socials**](https://jjjonesjr33.com/).

## Supported Devices
### This has been reworked to work with the following devices

* Granary Smart Feeder (PLAF103)
* Granary Smart Camera Feeder (PLAF203)
* One RFID Smart Feeder (PLAF301)
* Dockstream Smart Fountain (PLWF105)
* Dockstream RFID Smart Fountain (PLWF305)

### Some Devices / May or may not work as intended

* If you have a device that you would like added please issue a [request](https://github.com/jjjonesjr33/petlibro/issues/new/choose).

# Device Preview

## One RFID Smart Feeder (PLAF301) Features
Device Information

    Model
    Manufacturer
    Firmware Version

Features & Sensors

    Battery Status
    Buttons Lock
    Desiccant Remaining Days
    Device SN
    Food Dispenser Status
    Food Status
    Lid Status
    MAC Address
    Sleep Mode

Feeding Statistics

    Today's Eating Times
    Today's Feeding Plan
    Today's Feeding Quantity
    Today's Feeding Times
    Today's Total Eating Time

Connectivity

    Wi-Fi Status
    Wi-Fi Signal Strength
    Wi-Fi SSID

Configuration Options

    Disable Feeding Plan
    Enable Feeding Plan
    Manual Feed

## One RFID Smart Feeder Preview
![One RFID Smart Feeder](https://github.com/user-attachments/assets/0636003e-04ab-495c-8f28-d032610c9b19)

## Dockstream Smart RFID (PLWF305) Features
Device Information

    Model
    Manufacturer
    Firmware Version
    Hardware Version

Features & Sensors

    Current Weight
    Device Serial Number
    MAC Address
    Remaining Cleaning Days
    Remaining Filter Day
    Remaining Water
    Water Interval
    Water Time Duration

Connectivity

    Wi-Fi Status
    Wi-Fi Signal Strength
    Wi-Fi SSID

## Dockstream RFID Smart Fountain Preview
![Dockstream RFID Smart Fountain](https://github.com/user-attachments/assets/45622291-5eae-4a83-87ea-b98a8749b8f8)

# In Devlopment
* This is still a WIP integration, features may or may not be removed at any time. If you have suggestions please let me know.
- Features missing, but in the works.

  > Buttons to reset Cleaning/Filter/Desiccant - (PLAF103), (PLAF203), (PLAF301), (PLWF105), (PLWF305)

  > Switches to be added - Child Lock/Button Lock, Screen/Display, and Volume - (PLAF103), (PLAF203), (PLAF301)

  > Tracking RFID per pet intance eat/drink - Both (PLAF301) & (PLWF305) - Currently missing the API to setup tracking.

  > Live camera feed for Granary Smart Camera Feeder (PLAF203) - Currently missing the API to setup live stream.

# NOTICE
Alpha/Beta State Notice for this Plugin:

When setting up for the first time, please sign in and allow 1-5 minutes for the login process and data retrieval to complete. If you do not see all the sensors and controls listed, you may need to refresh your web browser's cache.

I recommend performing a full reboot of Home Assistant to ensure you are logged in and that the add-on has refreshed the data without any errors.

  > The addon is programmed to update every 60 seconds.

## Troubleshooting
To troubleshoot your Home Assistant instance, you can add the following configuration to your configuration.yaml file:

```yaml
logger:
  default: warning  # Default log level for all components
  logs:
    custom_components.petlibro: debug    # Enable debug logging for your component
```

## Installation

### Manually

Get the folder `custom_components/petlibro` in your HA `config/custom_components`


### Via [HACS](https://hacs.xyz/)
<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=jjjonesjr33&repository=petlibro&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

## Configuration
<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=petlibro" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>

- Enter your credentials.

  > Only one device can be login at the same time.
  >
  > If you to wan to keep your phone connected, create another account for this integration and share your device to it.
