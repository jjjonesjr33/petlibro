"""Support for PETLIBRO binary sensors."""
from __future__ import annotations
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from dataclasses import dataclass
from collections.abc import Callable
from functools import cached_property
from typing import Optional
import logging
from .const import DOMAIN
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary


_LOGGER = logging.getLogger(__name__)

from .devices import Device
from .devices.device import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.granary_feeder import GranaryFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription


@dataclass(frozen=True)
class PetLibroBinarySensorEntityDescription(BinarySensorEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device binary sensor entities."""

    device_class_fn: Callable[[_DeviceT], BinarySensorDeviceClass | None] = lambda _: None
    should_report: Callable[[_DeviceT], bool] = lambda _: True
    device_class: Optional[BinarySensorDeviceClass] = None

class PetLibroBinarySensorEntity(PetLibroEntity[_DeviceT], BinarySensorEntity):
    """PETLIBRO sensor entity."""

    entity_description: PetLibroBinarySensorEntityDescription[_DeviceT]

    @cached_property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        return self.entity_description.device_class

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        # Check if the binary sensor should report its state
        if not self.entity_description.should_report(self.device):
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

        # Return the state, ensuring it's a boolean
        return bool(state)

DEVICE_BINARY_SENSOR_MAP: dict[type[Device], list[PetLibroBinarySensorEntityDescription]] = {
    GranaryFeeder: [],
    OneRFIDSmartFeeder: [
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="door_state",
            translation_key="door_state",
            icon="mdi:door",
            device_class=BinarySensorDeviceClass.DOOR,
            should_report=lambda device: device.door_state is not None,
            name="Lid"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="food_dispenser_state",
            translation_key="food_dispenser_state",
            icon="mdi:bowl-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_dispenser_state is not None,
            name="Food Dispenser"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="door_blocked",
            translation_key="door_blocked",
            icon="mdi:door",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.door_blocked is not None,
            name="Lid Status"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
            name="Food Status"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            device_class=BinarySensorDeviceClass.POWER,
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            should_report=lambda device: device.enable_low_battery_notice is not None,
            name="Battery Status"
        )
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroBinarySensorEntityDescription[DockstreamSmartRFIDFountain](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        )
    ]
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO binary sensors using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded (if load_devices is not already called elsewhere)
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during binary sensor setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create binary sensor entities for each device based on the binary sensor map
    entities = [
        PetLibroBinarySensorEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_BINARY_SENSOR_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No binary sensors added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro binary sensors", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding binary sensor entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add binary sensor entities to Home Assistant
        async_add_entities(entities)

