"""Support for PETLIBRO buttons."""
from __future__ import annotations
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic
from logging import getLogger
import time
from .const import DOMAIN
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
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

_LOGGER = getLogger(__name__)

@dataclass(frozen=True)
class RequiredKeysMixin(Generic[_DeviceT]):
    """A class that describes devices button entity required keys."""
    set_fn: Callable[[_DeviceT], Coroutine[Any, Any, None]]
    command: str = ""  # Command name for command queue


@dataclass(frozen=True)
class PetLibroButtonEntityDescription(ButtonEntityDescription, PetLibroEntityDescription[_DeviceT], RequiredKeysMixin[_DeviceT]):
    """A class that describes device button entities."""
    entity_category: EntityCategory = EntityCategory.CONFIG


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


class EnhancedPetLibroButtonEntity(EnhancedPetLibroEntity[_DeviceT], ButtonEntity):
    """Enhanced PETLIBRO button entity with improved reliability features."""
    
    entity_description: PetLibroButtonEntityDescription[_DeviceT]
    
    def __init__(
        self, 
        device: _DeviceT, 
        hub: PetLibroHub, 
        description: PetLibroButtonEntityDescription[_DeviceT]
    ) -> None:
        """Initialize the enhanced button."""
        super().__init__(device, hub, description)
        self._last_pressed = None
        
    async def async_press(self) -> None:
        """Handle the button press with command queue support."""
        _LOGGER.debug("Pressing button: %s for device %s", self.entity_description.name, self.device.name)
        
        try:
            # Record the press time
            self._last_pressed = time.time()
            
            # Use command queue if available and command is specified
            if (hasattr(self.device, "execute_command") and 
                self.entity_description.command and 
                hasattr(self.device, "_command_queue") and 
                self.device._command_queue):
                
                _LOGGER.debug("Using command queue for button press: %s", self.entity_description.name)
                await self.device.execute_command(self.entity_description.command)
                
            else:
                # Fallback to direct function call
                _LOGGER.debug("Using direct function call for button press: %s", self.entity_description.name)
                await self.entity_description.set_fn(self.device)
                
            # Refresh the device state after the button press
            _LOGGER.debug("Successfully pressed button: %s", self.entity_description.name)
            
        except Exception as e:
            _LOGGER.error(
                f"Error pressing button {self.entity_description.name} for device {self.device.name}: {e}",
                exc_info=True  # Log full traceback for better debugging
            )
            raise
    
    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes with command information."""
        attrs = super().extra_state_attributes or {}
        
        # Add last pressed timestamp if available
        if self._last_pressed:
            attrs["last_pressed"] = self._last_pressed
            
            # Add human-readable time
            from datetime import datetime
            attrs["last_pressed_time"] = datetime.fromtimestamp(self._last_pressed).strftime("%Y-%m-%d %H:%M:%S")
            
            # Add age in minutes
            attrs["minutes_since_pressed"] = int((time.time() - self._last_pressed) / 60)
        
        # Add command info if available
        if self.entity_description.command:
            attrs["command"] = self.entity_description.command
            
        # Add pending command info if applicable
        if (hasattr(self.hub, "command_queue") and self.hub.command_queue and 
            hasattr(self.device, "serial") and self.entity_description.command):
            
            pending_commands = [
                cmd for cmd in self.hub.command_queue.queue
                if getattr(cmd, "device_id", "") == self.device.serial and 
                getattr(cmd, "command", "") == self.entity_description.command
            ]
            
            if pending_commands:
                attrs["pending_commands"] = len(pending_commands)
                
                # Add most recent pending command details
                newest = sorted(pending_commands, key=lambda x: getattr(x, "created_at", 0), reverse=True)[0]
                attrs["pending_since"] = getattr(newest, "created_at", None)
                attrs["pending_retries"] = getattr(newest, "retries", 0)
                
        return attrs


# Map buttons to their respective device types
DEVICE_BUTTON_MAP: dict[type[Device], list[PetLibroButtonEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            command="manual_feed",
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            command="set_feeding_plan",
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            command="set_feeding_plan",
            name="Disable Feeding Plan"
        )
    ],
    GranarySmartFeeder: [
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            command="manual_feed",
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            command="set_feeding_plan",
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            command="set_feeding_plan",
            name="Disable Feeding Plan"
        )
    ],
    GranarySmartCameraFeeder: [
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            command="manual_feed",
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            command="set_feeding_plan",
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            command="set_feeding_plan",
            name="Disable Feeding Plan"
        )
    ],
    OneRFIDSmartFeeder: [
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            command="manual_feed",
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            command="set_feeding_plan",
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            command="set_feeding_plan",
            name="Disable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="manual_lid_open",
            translation_key="manual_lid_open",
            set_fn=lambda device: device.set_manual_lid_open(),
            command="manual_lid_open",
            name="Manually Open Lid"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="display_on",
            translation_key="display_on",
            set_fn=lambda device: device.set_display_on(),
            command="set_display_switch",  # Assuming there's a command function
            name="Turn On Display"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="display_off",
            translation_key="display_off",
            set_fn=lambda device: device.set_display_off(),
            command="set_display_switch",  # Assuming there's a command function
            name="Turn Off Display"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="sound_on",
            translation_key="sound_on",
            set_fn=lambda device: device.set_sound_on(),
            command="set_sound_switch",  # Assuming there's a command function
            name="Turn On Sound"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="sound_off",
            translation_key="sound_off",
            set_fn=lambda device: device.set_sound_off(),
            command="set_sound_switch",  # Assuming there's a command function
            name="Turn Off Sound"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="desiccant_reset",
            translation_key="desiccant_reset",
            set_fn=lambda device: device.set_desiccant_reset(),
            command="reset_desiccant",  # Assuming there's a command function
            name="Desiccant Replaced"
        )
    ],
    PolarWetFoodFeeder: [
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="ring_bell",
            translation_key="ring_bell",
            set_fn=lambda device: device.feed_audio(),
            command="feed_audio",
            name="Ring Bell"
        ),
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="rotate_food_bowl",
            translation_key="rotate_food_bowl",
            set_fn=lambda device: device.rotate_food_bowl(),
            command="rotate_food_bowl",
            name="Rotate Food Bowl"
        )
    ],
    SpaceSmartFeeder: [
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            command="manual_feed",
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            command="set_feeding_plan",
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            command="set_feeding_plan",
            name="Disable Feeding Plan"
        ),
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
    entities = []
    
    for device in devices:
        for device_type, entity_descriptions in DEVICE_BUTTON_MAP.items():
            if isinstance(device, device_type):
                for description in entity_descriptions:
                    entities.append(EnhancedPetLibroButtonEntity(device, hub, description))

    if not entities:
        _LOGGER.warning("No buttons added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro buttons", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding button entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add button entities to Home Assistant
        async_add_entities(entities)
