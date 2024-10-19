"""Support for PETLIBRO buttons."""
from __future__ import annotations
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic
from logging import getLogger
from .const import DOMAIN
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary

_LOGGER = getLogger(__name__)

from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription
from .devices import Device
from .devices.device import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.granary_smart_feeder import GranarySmartFeeder
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain

@dataclass(frozen=True)
class RequiredKeysMixin(Generic[_DeviceT]):
    """A class that describes devices button entity required keys."""
    set_fn: Callable[[_DeviceT], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class PetLibroButtonEntityDescription(ButtonEntityDescription, PetLibroEntityDescription[_DeviceT], RequiredKeysMixin[_DeviceT]):
    """A class that describes device button entities."""
    entity_category: EntityCategory = EntityCategory.CONFIG


# Map buttons to their respective device types
DEVICE_BUTTON_MAP: dict[type[Device], list[PetLibroButtonEntityDescription]] = {
    Feeder: [
    ],
    GranarySmartFeeder: [
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Plan"
        )
    ],
    GranarySmartCameraFeeder: [
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Plan"
        )
    ],
    OneRFIDSmartFeeder: [
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Plan"
        )
    ],
    DockstreamSmartFountain: [
    ],
    DockstreamSmartRFIDFountain: [
    ],
}

class PetLibroButtonEntity(PetLibroEntity[_DeviceT], ButtonEntity):
    """PETLIBRO button entity."""
    entity_description: PetLibroButtonEntityDescription[_DeviceT]

    @property
    def available(self) -> bool:
        """Check if the device is available."""
        return getattr(self.device, 'online', False)

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Pressing button: %s for device %s", self.entity_description.name, self.device.name)

        # Log available methods for debugging
        _LOGGER.debug("Available methods for device %s: %s", self.device.name, dir(self.device))

        try:
            await self.entity_description.set_fn(self.device)
            await self.device.refresh()  # Refresh the device state after the button press
            _LOGGER.debug("Successfully pressed button: %s", self.entity_description.name)
        except Exception as e:
            _LOGGER.error(
                f"Error pressing button {self.entity_description.name} for device {self.device.name}: {e}",
                exc_info=True  # Log full traceback for better debugging
            )

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO buttons using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during button setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create button entities for each device based on the button map
    entities = [
        PetLibroButtonEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_BUTTON_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No buttons added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro buttons", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding button entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add button entities to Home Assistant
        async_add_entities(entities)




