"""Helpers for Petlibro devices."""

from collections.abc import Iterable
import logging
from typing import Literal

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..hub import PetLibroHub

_LOGGER = logging.getLogger(__name__)

DEVICES = "devices"


class DevicesHelper:
    """."""

    def __init__(
        self, *, hass: HomeAssistant, config_entry: ConfigEntry, hub: PetLibroHub
    ):
        """Initialise the DevicesHelper class."""
        self.hass = hass
        self.entry = config_entry
        self.handler = self.entry.entry_id
        self.hub = hub
        self.member = self.hub.member

        self.loaded_device_sn = set()
        _LOGGER.debug("Devices Helper initialised.")

    @property
    def cached_devices(self) -> dict:
        """Device info saved to the Config Entry options table."""
        return self.entry.options.get(DEVICES, {})

    def _remove_device(self, device_id: str) -> None:
        """Remove a device entry from Home Assistant."""
        self.hub.device_register.async_update_device(
            device_id=device_id,
            remove_config_entry_id=self.handler,
        )
        _LOGGER.debug("Removed device: %s", device_id)

    def _sync_cache(self, new_devices_cache: dict) -> None:
        """Sync new devices info to the Config Entry options table."""
        if new_devices_cache != self.cached_devices:
            self.hub.update_options({DEVICES: new_devices_cache})

    async def remove_device_entries(
        self, serials: str | Iterable[str] | Literal["all"], *, keep: bool = False
    ):
        """Remove device entries from Home Assistant.

        Args:
            serials: Serial(s) to act on, or "all".
            keep: Removes all devices *except* the given ones.
        """
        if isinstance(serials, str) and serials != "all":
            serials = [serials]

        new_devices_cache = self.cached_devices.copy()
        for serial, device in self.cached_devices.items():
            device: dict
            device_id = device.get("device_id")

            if not self.hub.device_register.async_get(device_id):
                new_devices_cache.pop(serial)
                _LOGGER.debug(
                    "Device ID %s for device serial %s not found, removing from config entry options.",
                    device_id,
                    serial,
                )
                continue

            matches = serials == "all" or serial in serials
            should_remove = matches if not keep else not matches

            if should_remove:
                self._remove_device(device_id)

        self._sync_cache(new_devices_cache)
