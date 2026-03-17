![Logo](https://raw.githubusercontent.com/jjjonesjr33/ha_petlibro/master/docs/media/logo.png)

---
# PETLIBRO integration for Home Assistant
[![version][versionbadge]][versionlink] [![release][releasebadge]][releaselink] [![community][communitybadge]][communitylink] [![hainstall][hainstallbadge]][hainstall] [![starsbadge][starsbadge]][stars] [![hacs_badge][hacsbadge]][hacs]

## Supporting the development
[![sponsor][sponsorbadge]][sponsorlink] [![discord][discordsponsorbadge]][discordsponsorlink] [![discord][discordbadge]][discordlink] [![patreon][patreonbadge]][patreonlink] [![kofibadge][kofibadge]][kofi] [![BuyMeCoffee][buymecoffeebadge]][buymecoffee] [![PayPal][paypalbadge]][paypal]

If you enjoy this integration and want to support its development, please consider backing the [co-developers][developerslink]. On the [discussions board][developerslink], you’ll find their support links along with direct links to their GitHub profiles.

[![Developers][developersbadge]][developerslink] [![JJJonesJr33][JJJonesJr33badge]][JJJonesJr33link] [![C4-Dimitri][C4-Dimitribadge]][C4-Dimitrilink] [![FeliGoblin][FeliGoblinbadge]][FeliGoblinlink]

---

> [!IMPORTANT]  
> Before setting up the integration in Home Assistant, be sure to review the [Account Management](https://github.com/jjjonesjr33/petlibro/wiki/PetLibro-Account-Management) and [Password Limitations](https://github.com/jjjonesjr33/petlibro/wiki/PetLibro-Password-Limitation) sections in the wiki. This will help ensure a smooth and successful setup process.
---

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
* Dockstream 2 Smart Fountain | Plug-In Model (PLWF106) 
* Dockstream 2 Smart Fountain | Cordless Model (PLWF116)

### Litter Boxes
* Luma Smart Litter Box (PLLB001)

### Pending Device(s)

### Some Devices / May or may not work as intended

* If you have a device that you would like added please issue a [request](https://github.com/jjjonesjr33/petlibro/issues/new/choose).

# Have questions, or need support?
> [!TIP]
>* Most answers can be found in our [Wiki](https://github.com/jjjonesjr33/petlibro/wiki)
> and if they can't, try the [Discussions](https://github.com/jjjonesjr33/petlibro/discussions)
>* Or get ahold of me via direct message on [Discord](https://discord.com/invite/3hkWMry) - `Jamie Jones Jr` / `jjjonesjr33` previously  `JJJonesJr33#0001`

#### Also if you want to check out all the other things I do follow me on my [**Socials**](https://jjjonesjr33.com/).
[![Socials][socialsbadge]][socialslink]

# In Development
#### This is still a WIP integration, features may or may not be removed at any time. If you have suggestions please let me know.
> [!NOTE]
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

## Installation (Automatic)
> [!IMPORTANT]
> This is a HACS custom integration — not a Home Assistant Add-on. Don't try to add this repository as an add-on in Home Assistant.
> 
> The IMHO simplest way to install this integration is via the two buttons below ('_OPEN HACS REPOSITORY ON MY HA_' and '_ADD INTEGRATION TO MY HA_').


### Via [HACS](https://hacs.xyz/)
<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=jjjonesjr33&repository=petlibro&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

## Configuration
<a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=petlibro" target="_blank"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Open your Home Assistant instance and start setting up a new integration." /></a>

- Enter your credentials.

  > Only one account can be logged in at the same time.
  >
  > If you to want to keep your phone's app connected, create another account for this integration and share your device(s) to it.
  
## Installation (Manual)

1. **Download the latest release**  
   - Visit: https://github.com/jjjonesjr33/petlibro/releases  
   - Download the newest `.zip` file.

2. **Extract the ZIP file**  
   - Open or extract the downloaded archive using your file manager.

3. **Locate the integration folder**  
   - Inside the extracted files, find:  
     `custom_components/petlibro`

4. **Copy the Petlibro folder to Home Assistant**  
   - Place the folder into your Home Assistant config directory so the final path becomes:  
     ```
     config/custom_components/petlibro
     ```

5. **Restart Home Assistant**  
   - Go to: *Settings → System → Restart*  
   - Or restart the container/service manually.

6. **Verify installation**  
   - Navigate to *Settings → Devices & Services* and check that **Petlibro** appears.

---
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jjjonesjr33/petlibro&type=Date&theme=dark)](https://www.star-history.com/#jjjonesjr33/petlibro&Date)

[stars]: https://github.com/jjjonesjr33/petlibro/stargazers
[starsbadge]: https://img.shields.io/github/stars/jjjonesjr33/petlibro?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyByb2xlPSJpbWciIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgdmlld0JveD0iMCAwIDE2IDE2Ij48cGF0aCBzdHlsZT0iZmlsbDojY2NjY2NjIiBkPSJNOCAuMjVhLjc1Ljc1IDAgMCAxIC42NzMuNDE4bDEuODgyIDMuODE1IDQuMjEuNjEyYS43NS43NSAwIDAgMSAuNDE2IDEuMjc5bC0zLjA0NiAyLjk3LjcxOSA0LjE5MmEuNzUxLjc1MSAwIDAgMS0xLjA4OC43OTFMOCAxMi4zNDdsLTMuNzY2IDEuOThhLjc1Ljc1IDAgMCAxLTEuMDg4LS43OWwuNzItNC4xOTRMLjgxOCA2LjM3NGEuNzUuNzUgMCAwIDEgLjQxNi0xLjI4bDQuMjEtLjYxMUw3LjMyNy42NjhBLjc1Ljc1IDAgMCAxIDggLjI1Wm0wIDIuNDQ1TDYuNjE1IDUuNWEuNzUuNzUgMCAwIDEtLjU2NC40MWwtMy4wOTcuNDUgMi4yNCAyLjE4NGEuNzUuNzUgMCAwIDEgLjIxNi42NjRsLS41MjggMy4wODQgMi43NjktMS40NTZhLjc1Ljc1IDAgMCAxIC42OTggMGwyLjc3IDEuNDU2LS41My0zLjA4NGEuNzUuNzUgMCAwIDEgLjIxNi0uNjY0bDIuMjQtMi4xODMtMy4wOTYtLjQ1YS43NS43NSAwIDAgMS0uNTY0LS40MUw4IDIuNjk0WiI+PC9wYXRoPjwvc3ZnPg==&label=Stars&color=ffffff

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-black.svg?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=ccc

[hainstall]: https://my.home-assistant.io/redirect/config_flow_start/?domain=petlibro
[hainstallbadge]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&logo=home-assistant&logoColor=ccc&label=usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.petlibro.total

[versionlink]: https://github.com/jjjonesjr33/petlibro/releases
[versionbadge]: https://img.shields.io/github/manifest-json/v/jjjonesjr33/petlibro?filename=custom_components%2Fpetlibro%2Fmanifest.json&color=slateblue&style=for-the-badge

[releaselink]: https://github.com/jjjonesjr33/petlibro/releases
[releasebadge]: https://img.shields.io/github/v/release/jjjonesjr33/petlibro?style=for-the-badge&logo=github&logoColor=ccc

[communitylink]: https://community.home-assistant.io/t/petlibro-cloud-integration-non-tuya-wip/759978
[communitybadge]: https://img.shields.io/static/v1.svg?label=Community&message=Forum&color=41bdf5&logo=HomeAssistant&logoColor=white&style=for-the-badge

[developerslink]: https://github.com/jjjonesjr33/petlibro/discussions/56
[developersbadge]: https://img.shields.io/badge/Support%20a%20Developer-❤️-black?style=for-the-badge

[sponsorlink]: https://github.com/sponsors/jjjonesjr33
[sponsorbadge]: https://img.shields.io/badge/Become%20a%20Sponsor-GitHub-black?style=for-the-badge&logo=github&logoColor=white

[sponsorslink]: https://github.com/sponsors/jjjonesjr33
[sponsorsbadge]: https://img.shields.io/github/sponsors/jjjonesjr33?label=Sponsors&style=for-the-badge&logo=github&logoColor=ccc

[patreonlink]: https://www.patreon.com/c/JamieJonesJr
[patreonbadge]: https://img.shields.io/badge/Patreon-F96854?style=for-the-badge&logo=patreon&logoColor=white

[kofi]: https://ko-fi.com/jamiejonesjr
[kofibadge]: https://img.shields.io/badge/Ko--fi-FF5E5B?style=for-the-badge&logo=kofi&logoColor=ffffff

[buymecoffee]: https://www.buymeacoffee.com/jamiejonesjr
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a-coffee-yellow.svg?style=for-the-badge&logo=buymeacoffee&logoColor=ccc

[paypal]: https://paypal.me/jjjonesjr33
[paypalbadge]: https://img.shields.io/badge/paypal-me-blue.svg?style=for-the-badge&logo=paypal&logoColor=ccc

[discordsponsorlink]: https://discord.com/servers/jones-inc-541574294656909312
[discordsponsorbadge]: https://img.shields.io/badge/Support%20on-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white

[discordlink]: https://discord.com/invite/3hkWMry
[discordbadge]: https://img.shields.io/discord/541574294656909312?style=for-the-badge&logo=discord&logoColor=white&color=5865F2

[socialslink]: https://jjjonesjr33.com
[socialsbadge]: https://img.shields.io/badge/Socials-JJJonesJr33-black?style=for-the-badge&logo=rss&logoColor=white

[JJJonesJr33link]: https://github.com/jjjonesjr33
[JJJonesJr33badge]: https://img.shields.io/badge/JJJonesJr33-GitHub-blue?style=for-the-badge&logo=github&logoColor=white

[C4-Dimitrilink]: https://github.com/C4-Dimitri
[C4-Dimitribadge]: https://img.shields.io/badge/C4%20Dimitri-GitHub-red?style=for-the-badge&logo=github&logoColor=white

[FeliGoblinlink]: https://github.com/FeliGoblin
[FeliGoblinbadge]: https://img.shields.io/badge/FeliGoblin-GitHub-green?style=for-the-badge&logo=github&logoColor=white
