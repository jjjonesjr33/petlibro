"""Support for PETLIBRO camera feeders (Granary Smart Camera Feeder, PLAF203).

By default the stream comes from a local go2rtc process running the clean-room
``petlibro://`` LAN transport (see go2rtc.py): no PETLIBRO account, vendor SDK,
or add-on is needed. The feeder's IP is taken from the ``camera_host`` option,
then from any device tracker reporting the feeder's MAC address, and otherwise
discovered by camera UID on Home Assistant's local network.

Users who already run their own bridge can set ``camera_stream_url`` instead.
"""
from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientError, ClientTimeout

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_CAMERA_HOST, CONF_CAMERA_STREAM_URL, DOMAIN, IntegrationSetting
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .entity import PetLibroEntity, PetLibroEntityDescription
from .go2rtc import Go2rtcRunner, Go2rtcUnavailable, petlibro_source
from .hub import PetLibroHub

_LOGGER = logging.getLogger(__name__)

CAMERA_DESCRIPTION = PetLibroEntityDescription[GranarySmartCameraFeeder](
    key="camera",
    translation_key="camera",
    name=None,  # take the device name
)


class PetLibroCamera(PetLibroEntity[GranarySmartCameraFeeder], Camera):
    """Live view of a Granary Smart Camera Feeder."""

    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        device: GranarySmartCameraFeeder,
        hub: PetLibroHub,
        runner: Go2rtcRunner | None,
        stream_url: str | None,
        host: str | None,
    ) -> None:
        """Initialise the camera entity."""
        PetLibroEntity.__init__(self, device, hub, CAMERA_DESCRIPTION)
        Camera.__init__(self)
        self._runner = runner
        self._stream_url = stream_url
        self._host = host

    @property
    def available(self) -> bool:
        """The camera is available while it is switched on in the app."""
        return super().available and self.device.enable_camera

    def _resolve_host(self) -> str | None:
        if self._host:
            return self._host
        mac = (self.device.mac or "").lower()
        if mac:
            for state in self.hass.states.async_all("device_tracker"):
                if str(state.attributes.get("mac", "")).lower() == mac:
                    if ip := state.attributes.get("ip"):
                        return str(ip)
        return None  # let go2rtc discover the camera by UID

    async def stream_source(self) -> str | None:
        """Return the RTSP URL of the live stream."""
        if self._stream_url:
            return self._stream_url
        if self._runner is None or not self.device.camera_id:
            return None
        source = petlibro_source(self.device.camera_id, self._resolve_host())
        try:
            return await self._runner.async_ensure_stream(self.device.serial, source)
        except Go2rtcUnavailable as err:
            _LOGGER.error("Camera stream for %s is unavailable: %s", self.device.name, err)
            return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still frame from the live stream."""
        if self._runner is None or await self.stream_source() is None:
            return None
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                self._runner.frame_url(self.device.serial), timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.debug("Snapshot for %s failed: HTTP %s", self.device.name, resp.status)
        except (ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Snapshot for %s failed: %s", self.device.name, err)
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO cameras from a config entry."""
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    feeders = [
        device
        for device in hub.devices.values()
        if isinstance(device, GranarySmartCameraFeeder)
    ]
    if not feeders:
        return

    stream_url = (entry.options.get(CONF_CAMERA_STREAM_URL) or "").strip() or None
    host = (entry.options.get(CONF_CAMERA_HOST) or "").strip() or None
    enabled = entry.options.get(IntegrationSetting.CAMERA_STREAM, IntegrationSetting.CAMERA_STREAM.default)
    if not stream_url and not enabled:
        _LOGGER.debug("Camera streaming is disabled in the integration settings")
        return

    runner: Go2rtcRunner | None = None
    if not stream_url:
        runner = Go2rtcRunner(hass, entry.entry_id)

        async def _async_stop(_event: Event | None = None) -> None:
            await runner.async_stop()

        entry.async_on_unload(_async_stop)
        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop))
        entry.async_create_background_task(
            hass, _async_prepare(runner), "petlibro go2rtc download"
        )

    async_add_entities(
        PetLibroCamera(device, hub, runner, stream_url, host) for device in feeders
    )


async def _async_prepare(runner: Go2rtcRunner) -> None:
    try:
        await runner.async_prepare()
    except Go2rtcUnavailable as err:
        _LOGGER.error("Camera streaming is unavailable: %s", err)
