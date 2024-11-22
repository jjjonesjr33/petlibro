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
        """Return True if the number sensor is on."""
        # Check if the number entity should report its state
        if not self.entity_description.value(self.device):
            return False

        # Retrieve the state using getattr, defaulting to None if the attribute is missing
        state = getattr(self.device, self.entity_description.key, None)

        # Check if this is the first time the sensor is being refreshed by checking if _last_state exists
        last_state = getattr(self, '_last_state', None)
        initial_log_done = getattr(self, '_initial_log_done', False)  # Track if we've logged the initial state

        # If this is the initial boot, don't log anything but track the state
        if not initial_log_done:
            # Mark the initial log as done without logging
            self._initial_log_done = True  
        elif last_state != state:
            # Log state changes: log online with INFO and offline with WARNING
            if state:
                _LOGGER.info(f"Device {self.device.name} is online.")
            else:
                _LOGGER.warning(f"Device {self.device.name} is offline.")

        # Store the last state for future comparisons
        self._last_state = state

        # Return the state, ensuring it's a float
        return float(state)

DEVICE_NUMBER_MAP: dict[type[Device], list[PetLibroNumberEntityDescription]] = {
    Feeder: [
    ],
    OneRFIDSmartFeeder: [
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="sound_level",
            translation_key="sound_level",
            icon="mdi:volume-high",
            native_unit_of_measurement="%",
            native_max_value=100,
            native_min_value=1,
            native_step=1,
            value=lambda device: device.sound_level,
            method=lambda device, value: device.set_sound_level(device.serial, value), # Pass both serial and value
            name="Sound Level"
        ),
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

