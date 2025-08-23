[![version](https://img.shields.io/github/manifest-json/v/jjjonesjr33/petlibro?filename=custom_components%2Fpetlibro%2Fmanifest.json&color=slateblue)](https://github.com/jjjonesjr33/petlibro/releases)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/jjjonesjr33/petlibro)
[![Community Forum](https://img.shields.io/static/v1.svg?label=Community&message=Forum&color=41bdf5&logo=HomeAssistant&logoColor=white)](https://community.home-assistant.io/t/petlibro-cloud-integration-non-tuya-wip/759978)
[![Become a Sponsor](https://img.shields.io/badge/Become%20a%20Sponsor-❤️-black)](https://github.com/sponsors/jjjonesjr33)
[![Sponsors](https://img.shields.io/github/sponsors/jjjonesjr33?label=Sponsors)](https://github.com/sponsors/jjjonesjr33)
![Logo](https://raw.githubusercontent.com/jjjonesjr33/ha_petlibro/master/docs/media/logo.png)
> [!IMPORTANT]  
> Before setting up the integration in Home Assistant, be sure to review the [Account Management](https://github.com/jjjonesjr33/petlibro/wiki/PetLibro-Account-Management) and [Password Limitations](https://github.com/jjjonesjr33/petlibro/wiki/PetLibro-Password-Limitation) sections in the wiki. This will help ensure a smooth and successful setup process.

# PETLIBRO integration for Home Assistant

### Account Integration
#### Manage your Petlibro account directly within Home Assistant

* View account information (email, username, region, subscription status)
* Update profile details
* Configure time zone and language preferences
* Manage linked devices at the account level
* Access support and diagnostic information
* Options Flow in Home Assistant (⚙️ Configure button) for account settings

### Supported Devices
#### This has been reworked to work with the following devices

### Feeders
* Granary Smart Feeder (PLAF103) | Version 2
* Space Smart Feeder (PLAF107)
* Air Smart Feeder (PLAF108)
* Polar Wet Food Feeder (PLAF109)
* Granary Smart Camera Feeder (PLAF203)
* One RFID Smart Feeder (PLAF301)

### Fountains
* Dockstream Smart Fountain (PLWF105)
* Dockstream RFID Smart Fountain (PLWF305)
* Dockstream 2 Smart Cordless Fountain (PLWF116)

### Some Devices / May or may not work as intended

* If you have a device that you would like added please issue a [request](https://github.com/jjjonesjr33/petlibro/issues/new/choose).

# Have questions, or need support?
> [!TIP]
>* Most answers can be found in our [Wiki](https://github.com/jjjonesjr33/petlibro/wiki)
> and if they can't, try the [Discussions](https://github.com/jjjonesjr33/petlibro/discussions)
>* Or get ahold of me via direct message on [Discord](https://discord.com/invite/3hkWMry) - `Jamie Jones Jr` / `jjjonesjr33` previously  `JJJonesJr33#0001`

#### Also if you want to check out all the other things I do follow me on my [**Socials**](https://jjjonesjr33.com/).

# In Development
#### This is still a WIP integration, features may or may not be removed at any time. If you have suggestions please let me know.
> [!NOTE]
  >* Switches to be added - Child Lock/Button Lock, Screen/Display, and Volume - (PLAF103), (PLAF203), (PLAF301)
  >* Tracking RFID per pet intance eat/drink - (PLWF305) - API Information gathered, working on implementation.
  >* Live camera feed for Granary Smart Camera Feeder (PLAF203) - Currently missing the API to setup live stream. Seems to connect via Kalay TUTK, if you have any experience integrating with this platform, please reach out to help us implement this.

# NOTICE
#### Alpha/Beta state notice for this plugin:
> [!WARNING]
>* When setting up for the first time, please sign in and allow 1-5 minutes for the login process and data retrieval to complete. If you do not see all the sensors and controls listed, you may need to refresh your web browser's cache.
>* I recommend performing a full reboot of Home Assistant to ensure you are logged in and that the add-on has refreshed the data without any errors. 
>* The addon is programmed to update every 60 seconds.

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

  > Only one device can be logged in at the same time.
  >
  > If you to want to keep your phone's app connected, create another account for this integration and share your device to it.

## Star History

<a href="https://www.star-history.com/#jjjonesjr33/petlibro&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=jjjonesjr33/petlibro&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=jjjonesjr33/petlibro&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=jjjonesjr33/petlibro&type=Date" />
 </picture>
</a>
