"""Support for PETLIBRO text entities."""
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
from homeassistant.components.text import (
    TextEntity,
    TextEntityDescription,
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
class PetLibroTextEntityDescription(TextEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device text entities."""
    native_value: Callable[[_DeviceT], str] = lambda _: True

class PetLibroTextEntity(PetLibroEntity[_DeviceT], TextEntity):
    """PETLIBRO text entity."""

    entity_description: PetLibroTextEntityDescription[_DeviceT]

    @property
    def native_value(self) -> str | None:
        """Return the current current_option."""
        state = getattr(self.device, self.entity_description.key, None)
        if state is None:
            _LOGGER.warning(f"Current option '{self.entity_description.key}' is None for device {self.device.name}")
            return None
        _LOGGER.debug(f"Retrieved current option for '{self.entity_description.key}', {self.device.name}: {state}")
        return str(state)
    
    async def async_set_value(self, value: str) -> None:
        """Set the current_option of the text."""
        _LOGGER.debug(f"Setting current option {value} for {self.device.name}")
        # Dont do anything after setting the text. we will only do something on selection from the select entity.

DEVICE_TEXT_MAP: dict[type[Device], list[PetLibroTextEntityDescription]] = {
    Feeder: [
    ],
    OneRFIDSmartFeeder: [
        PetLibroTextEntityDescription[OneRFIDSmartFeeder](
            key="display_text",
            translation_key="display_text",
            icon="mdi:text-recognition",
            mode="text",
            native_max=100,
            native_min=1,
            pattern=r"^(?!\s*$)[a-zA-Z0-9 ]{1,20}$",
            native_value=lambda device: device.display_text,
            name="Text on Display"
        )
    ]
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO text using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded (if load_devices is not already called elsewhere)
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during text setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create text entities for each device based on the text map
    entities = [
        PetLibroTextEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_TEXT_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No text entities added, entities list is empty!")
    else:
        # Log the text of entities and their details
        _LOGGER.debug("Adding %d PetLibro text entities", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding text entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add text entities to Home Assistant
        async_add_entities(entities)

