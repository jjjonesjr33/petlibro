"""Support for PETLIBRO text entities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity, TextEntityDescription

from .const import DOMAIN
from .devices.feeders.air_smart_feeder import AirSmartFeeder
from .devices.feeders.feeder import Feeder
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .devices.feeders.granary_smart_feeder import GranarySmartFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.feeders.polar_wet_food_feeder import PolarWetFoodFeeder
from .devices.feeders.space_smart_feeder import SpaceSmartFeeder
from .devices.fountains.dockstream_2_smart_cordless_fountain import (
    Dockstream2SmartCordlessFountain,
)
from .devices.fountains.dockstream_2_smart_fountain import Dockstream2SmartFountain
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import (
    DockstreamSmartRFIDFountain,
)
from .entity import PetLibroEntity, PetLibroEntityDescription, _DeviceT

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .devices import Device

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PetLibroTextEntityDescription(
    TextEntityDescription, PetLibroEntityDescription[_DeviceT]
):
    """A class that describes device text entities."""

    native_value: Callable[[_DeviceT], str] = lambda _: True


class PetLibroTextEntity(PetLibroEntity[_DeviceT], TextEntity):
    """PETLIBRO text entity."""

    entity_description: PetLibroTextEntityDescription[_DeviceT]

    @property
    def native_value(self) -> str | None:
        """Return the current display text."""
        return self.device.display_text

    async def async_set_value(self, native_value: str) -> None:
        """Set the current text value."""
        _LOGGER.debug("Setting value %s for %s", native_value, self.device.name)
        try:
            if not native_value:
                _LOGGER.warning("Empty value provided for %s", self.device.name)
                return
            # Set text to uppercase as this is what API accepts.
            uppercase_value = native_value.upper()
            _LOGGER.debug(
                "Calling method with value=%s for %s", uppercase_value, self.device.name
            )
            await self.device.set_display_text(uppercase_value)
            # Update value in HA to uppercase as well
            self.device.display_text = uppercase_value
            _LOGGER.debug(
                "Original: %s, Uppercased: %s for %s",
                native_value,
                uppercase_value,
                self.device.name,
            )
            self.async_write_ha_state()
        except Exception:
            _LOGGER.exception(
                "Error setting value %s for %s", native_value, self.device.name
            )


DEVICE_TEXT_MAP: dict[type[Device], list[PetLibroTextEntityDescription]] = {
    Feeder: [],
    AirSmartFeeder: [],
    GranarySmartFeeder: [],
    GranarySmartCameraFeeder: [],
    PolarWetFoodFeeder: [],
    OneRFIDSmartFeeder: [
        PetLibroTextEntityDescription[OneRFIDSmartFeeder](
            key="display_text",
            translation_key="display_text",
            icon="mdi:text-recognition",
            mode="text",
            native_max=100,
            native_min=1,
            pattern=r"^(?!\s*$)[a-zA-Z0-9 ]{1,20}$",
            name="Text on Display",
        )
    ],
    SpaceSmartFeeder: [],
    DockstreamSmartFountain: [],
    DockstreamSmartRFIDFountain: [],
    Dockstream2SmartFountain: [],
    Dockstream2SmartCordlessFountain: [],
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
            _LOGGER.debug(
                "Adding text entity: %s for device %s",
                entity.entity_description.name,
                entity.device.name,
            )

        # Add text entities to Home Assistant
        async_add_entities(entities)
