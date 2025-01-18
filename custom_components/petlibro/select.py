"""Support for PETLIBRO selects."""
from __future__ import annotations
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from dataclasses import dataclass
from dataclasses import dataclass, field
from collections.abc import Callable
from functools import cached_property
from typing import Optional
from typing import Any
from typing import List, Awaitable
import logging
from .const import DOMAIN
from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary


_LOGGER = logging.getLogger(__name__)

from .devices import Device
from .devices.device import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.air_smart_feeder import AirSmartFeeder
from .devices.feeders.granary_smart_feeder import GranarySmartFeeder
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.feeders.polar_wet_food_feeder import PolarWetFoodFeeder
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription

@dataclass(frozen=True)
class PetLibroSelectEntityDescription(SelectEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device select entities."""

    method: Callable[[_DeviceT, str], Awaitable[None]]
    options: List[str]
    current_option: Callable[[_DeviceT], str] = lambda _: True

class PetLibroSelectEntity(PetLibroEntity[_DeviceT], SelectEntity):
    """PETLIBRO sensor entity."""

    entity_description: PetLibroSelectEntityDescription[_DeviceT]

    @property
    def current_option(self) -> str:
        """Return the current current_option."""
        state = getattr(self.device, self.entity_description.key, None)
        if state is None:
            _LOGGER.warning(f"Current option '{self.entity_description.key}' is None for device {self.device.name}")
            return None
        _LOGGER.debug(f"Retrieved current option for '{self.entity_description.key}', {self.device.name}: {state}")
        return str(state)
    
    async def async_select_option(self, current_option: str) -> None:
        """Set the current_option of the select."""
        _LOGGER.debug(f"Setting current option {current_option} for {self.device.name}")
        try:
            _LOGGER.debug(f"Calling method with current option={current_option} for {self.device.name}")
            await self.entity_description.method(self.device, current_option)
            _LOGGER.debug(f"Current option {current_option} set successfully for {self.device.name}")
        except Exception as e:
            _LOGGER.error(f"Error setting current option {current_option} for {self.device.name}: {e}")

    @staticmethod
    def map_value_to_api(*, key: str, value: str) -> str:
        """Map user-friendly values to API-compatible values."""
        mappings = {
            "lid_speed": {
                "Slow": "SLOW",
                "Medium": "MEDIUM",
                "Fast": "FAST"
            },
            "lid_mode": {
                "Stay Open": "KEEP_OPEN",
                "Open On Detection": "CUSTOM"
            }
        }
        return mappings.get(key, {}).get(value, "unknown")

DEVICE_SELECT_MAP: dict[type[Device], list[PetLibroSelectEntityDescription]] = {
    Feeder: [
    ],
    OneRFIDSmartFeeder: [
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="lid_speed",
            translation_key="lid_speed",
            icon="mdi:volume-high",
            current_option=lambda device: device.lid_speed,
            options=['Slow','Medium','Fast'],
            method=lambda device, current_option: device.set_lid_speed(PetLibroSelectEntity.map_value_to_api("lid_speed",current_option)),
            name="Lid Speed"
        ),
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="lid_mode",
            translation_key="lid_mode",
            icon="mdi:volume-high",
            current_option=lambda device: device.lid_mode,
            options=['Stay Open','Open On Detection'],
            method=lambda device, current_option: device.set_lid_speed(PetLibroSelectEntity.map_value_to_api("lid_mode",current_option)),
            name="Lid Mode"
        )
    ]
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO select using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded (if load_devices is not already called elsewhere)
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during select setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create select entities for each device based on the select map
    entities = [
        PetLibroSelectEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_SELECT_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No select entities added, entities list is empty!")
    else:
        # Log the select of entities and their details
        _LOGGER.debug("Adding %d PetLibro select entities", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding select entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add select entities to Home Assistant
        async_add_entities(entities)

