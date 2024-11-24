"""Support for PETLIBRO numbers."""
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
import logging
from .const import DOMAIN
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberDeviceClass,

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
class PetLibroNumberEntityDescription(NumberEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device number entities."""

    device_class_fn: Callable[[_DeviceT], NumberDeviceClass | None] = lambda _: None
    value: Callable[[_DeviceT], float] = lambda _: True
    method: Callable[[_DeviceT], float] = lambda _: True
    device_class: Optional[NumberDeviceClass] = None

class PetLibroNumberEntity(PetLibroEntity[_DeviceT], NumberEntity):
    """PETLIBRO sensor entity."""

    entity_description: PetLibroNumberEntityDescription[_DeviceT]

    @cached_property
    def device_class(self) -> NumberDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        return self.entity_description.device_class

    @property
    def value(self) -> float:
        """Return the current state."""
        state = getattr(self.device, self.entity_description.key, None)
        if state is None:
            _LOGGER.warning(f"Value '{self.entity_description.key}' is None for device {self.device.name}")
            return None
        _LOGGER.debug(f"Retrieved value for {self.device.name}: {state}")
        return float(state)
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        _LOGGER.debug(f"Setting value {value} for {self.device.name}")
        try:
            # Call the method with await since it's async
            await self.entity_description.method(self.device, value)
            _LOGGER.debug(f"Value {value} set successfully for {self.device.name}")
        except Exception as e:
            _LOGGER.error(f"Error setting value {value} for {self.device.name}: {e}")

DEVICE_NUMBER_MAP: dict[type[Device], list[PetLibroNumberEntityDescription]] = {
    Feeder: [
    ],
    OneRFIDSmartFeeder: [
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="desiccant_frequency",
            translation_key="desiccant_frequency",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value=lambda device: device.desiccant_frequency,
            method=lambda device, value: device.set_desiccant_frequency(value, type="DESICCANT"),
            name="Desiccant Frequency"
        ),
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="sound_level",
            translation_key="sound_level",
            icon="mdi:volume-high",
            native_unit_of_measurement="%",
            native_max_value=100,
            native_min_value=1,
            native_step=1,
            value=lambda device: device.sound_level,
            method=lambda device, value: device.set_sound_level(value),
            name="Sound Level"
        )
    ]
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO number using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded (if load_devices is not already called elsewhere)
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during number setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create number entities for each device based on the number map
    entities = [
        PetLibroNumberEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_NUMBER_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No number entities added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro number entities", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding number entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add number entities to Home Assistant
        async_add_entities(entities)

