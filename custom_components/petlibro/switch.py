"""Support for PETLIBRO switches."""
from __future__ import annotations
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Generic
import logging
from .const import DOMAIN
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .hub import PetLibroHub
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription, EnhancedPetLibroEntity
from .devices import Device
from .devices.device import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.air_smart_feeder import AirSmartFeeder
from .devices.feeders.granary_smart_feeder import GranarySmartFeeder
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.feeders.polar_wet_food_feeder import PolarWetFoodFeeder
from .devices.feeders.space_smart_feeder import SpaceSmartFeeder
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class RequiredKeysMixin(Generic[_DeviceT]):
    """A class that describes devices switch entity required keys."""

    set_fn: Callable[[_DeviceT, bool], Coroutine[Any, Any, None]]
    command_on: str = ""  # Command name for turning on using command queue
    command_off: str = ""  # Command name for turning off using command queue

@dataclass(frozen=True)
class PetLibroSwitchEntityDescription(SwitchEntityDescription, PetLibroEntityDescription[_DeviceT], RequiredKeysMixin[_DeviceT]):
    """A class that describes device switch entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG


class PetLibroSwitchEntity(PetLibroEntity[_DeviceT], SwitchEntity):
    """PETLIBRO switch entity."""

    entity_description: PetLibroSwitchEntityDescription[_DeviceT]  # type: ignore [reportIncompatibleVariableOverride]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return bool(getattr(self.device, self.entity_description.key))

    @property
    def available(self) -> bool:
        """Check if the device is available."""
        return getattr(self.device, 'online', False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.device, False)


class EnhancedPetLibroSwitchEntity(EnhancedPetLibroEntity[_DeviceT], SwitchEntity):
    """Enhanced PETLIBRO switch entity with improved reliability features."""

    entity_description: PetLibroSwitchEntityDescription[_DeviceT]  # type: ignore [reportIncompatibleVariableOverride]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return bool(getattr(self.device, self.entity_description.key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on using the command queue if available."""
        try:
            if hasattr(self.device, "execute_command") and self.entity_description.command_on:
                # Use the device's command queue
                command = self.entity_description.command_on
                await self.device.execute_command(command, value=True)
            else:
                # Legacy method
                await self.entity_description.set_fn(self.device, True)
        except Exception as ex:
            _LOGGER.error(f"Error turning on {self.name}: {ex}")
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off using the command queue if available."""
        try:
            if hasattr(self.device, "execute_command") and self.entity_description.command_off:
                # Use the device's command queue
                command = self.entity_description.command_off
                await self.device.execute_command(command, value=False)
            else:
                # Legacy method
                await self.entity_description.set_fn(self.device, False)
        except Exception as ex:
            _LOGGER.error(f"Error turning off {self.name}: {ex}")
            raise

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes with command and state information."""
        attrs = super().extra_state_attributes or {}
        
        # Add command info if available
        if hasattr(self.entity_description, "command_on") and self.entity_description.command_on:
            attrs["command_on"] = self.entity_description.command_on
        if hasattr(self.entity_description, "command_off") and self.entity_description.command_off:
            attrs["command_off"] = self.entity_description.command_off
            
        # Add last controlled timestamp if available
        if hasattr(self.device, "last_controlled") and getattr(self.device, "last_controlled", None):
            attrs["last_controlled"] = self.device.last_controlled
            
        # Add pending command info if applicable
        if hasattr(self.hub, "command_queue") and self.hub.command_queue:
            pending_commands = [
                cmd for cmd in self.hub.command_queue.queue
                if getattr(cmd, "device_id", "") == self.device.serial and 
                getattr(cmd, "command", "") in [
                    self.entity_description.command_on, 
                    self.entity_description.command_off
                ]
            ]
            
            if pending_commands:
                attrs["pending_commands"] = len(pending_commands)
        
        return attrs


DEVICE_SWITCH_MAP: dict[type[Device], list[PetLibroSwitchEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
    ],
    GranarySmartFeeder: [
    ],
    GranarySmartCameraFeeder: [
    ],
    OneRFIDSmartFeeder: [
    ],
    PolarWetFoodFeeder: [
        PetLibroSwitchEntityDescription[PolarWetFoodFeeder](
            key="manual_feed_now",
            translation_key="manual_feed_now",
            set_fn=lambda device, value: device.set_manual_feed_now(value),
            command_on="manual_feed_now",
            command_off="manual_feed_now",
            name="Manually Open/Close Lid"
        ),
    ],
    SpaceSmartFeeder: [
    ],
    DockstreamSmartFountain: [
    ],
    DockstreamSmartRFIDFountain: [
    ],
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO switches using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during switch setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create switch entities for each device based on the switch map
    entities = []
    
    for device in devices:
        for device_type, entity_descriptions in DEVICE_SWITCH_MAP.items():
            if isinstance(device, device_type):
                for description in entity_descriptions:
                    entities.append(EnhancedPetLibroSwitchEntity(device, hub, description))

    if not entities:
        _LOGGER.debug("No switches added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro switches", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding switch entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add switch entities to Home Assistant
        async_add_entities(entities)
