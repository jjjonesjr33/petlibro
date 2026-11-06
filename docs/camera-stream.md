# Live camera (Granary Smart Camera Feeder / PLAF203)

> Experimental. Tested on a PLAF203 with Home Assistant 2026.10 (amd64).

Each Granary Smart Camera Feeder gets a `camera` entity with live 1080p video
and audio. It works like any other Home Assistant camera: dashboards, snapshots,
and recordings.

## How it works

The feeder's camera uses a Kalay/TUTK-family UDP protocol on port `32761`,
which Home Assistant's bundled go2rtc does not support. The integration
therefore runs its own small go2rtc process that adds a clean-room
`petlibro://` source, written by
[@tannerln7](https://github.com/tannerln7) for
[Petlibro Local](https://github.com/tannerln7/Petlibro-Home-Assistant) (MIT).

- On first setup the integration downloads a static go2rtc build for your
  architecture (`amd64`, `aarch64`, or `armv7`) from a pinned release, checks
  it against a pinned SHA-256, and stores it under `/config/.petlibro/`.
- go2rtc listens on `127.0.0.1` only. Nothing is exposed to your network.
- No PETLIBRO account data, vendor SDK, or add-on is involved in streaming.
  The integration only reads the camera UID and MAC address from the cloud
  device record.

## Finding the feeder

The integration needs to reach the feeder on your LAN. It finds the feeder's
IP address in this order:

1. **Camera Feeder IP Address** in the integration settings, if set.
2. Any `device_tracker` entity that reports the feeder's MAC address, such as
   UniFi Network, Nmap, or a router integration. This works across VLANs.
3. Discovery by camera UID on Home Assistant's local network. This needs the
   feeder on the same subnet as Home Assistant.

If the camera never loads and the feeder is on another subnet, give it a DHCP
reservation and enter that address under **Settings > Devices & services >
PETLIBRO > Configure > Integration settings**. UDP port `32761` must be
reachable from Home Assistant.

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| Stream Camera Feeders | on | Turn the built-in camera stream off entirely. |
| Camera Feeder IP Address | empty | Fixed feeder address; see above. |
| Custom Camera Stream URL | empty | Use a stream from your own go2rtc or bridge instead of the built-in one. |

These settings only appear if your account has a camera feeder.

## Limitations

- The feeder allows roughly one live viewer session at a time. Watching in Home
  Assistant can briefly interrupt the PETLIBRO app's live view, and vice versa.
- The feeder's firmware may still need its normal cloud connection to accept
  local viewing sessions.
- Two-way audio is not supported.
