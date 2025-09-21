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
from homeassistant.core import callback
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
from .devices.feeders.space_smart_feeder import SpaceSmartFeeder
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain
from .devices.fountains.dockstream_2_smart_cordless_fountain import Dockstream2SmartCordlessFountain
from .devices.fountains.dockstream_2_smart_fountain import Dockstream2SmartFountain
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription


async def _apply_and_refresh(device, action_coro):
    await action_coro
    await device.refresh()

async def _current_schedule(device):
    """Return the best-known interval/duration from the device cache."""
    interval = int(getattr(device, "water_interval") or 0)
    duration = int(getattr(device, "water_dispensing_duration") or 0)
    return interval, duration

async def _apply_with_cached_schedule(device, builder):
    """
    Read the device's cached interval/duration, call the API builder(interval, duration),
    then refresh the device.
    """
    interval, duration = await _current_schedule(device)
    on = bool(getattr(device, "water_state", False))
    off = not on
    return await _apply_and_refresh(device, builder(interval, duration, off))

@dataclass(frozen=True)
class PetLibroSelectEntityDescription(SelectEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device select entities."""

    options_list: list[str] = field(default_factory=list)  # Default to empty list
    method: Callable[[_DeviceT, str], Any] = field(default=lambda _: True)  # Default lambda function
    current_selection: Callable[[_DeviceT], str] | None = None  # Default to None

class PetLibroSelectEntity(PetLibroEntity[_DeviceT], SelectEntity):
    """PETLIBRO select entity."""

    entity_description: PetLibroSelectEntityDescription[_DeviceT]

    @property
    def options(self) -> list[str]:
        """Return the list of available options for the select."""
        # This should return the options that are available for selection.
        # Use the options_list field from the entity_description.
        if self.entity_description.options_list:
            return self.entity_description.options_list
        else:
            # If there are no options, return an empty list or log an error.
            _LOGGER.error(f"No options available for select entity {self.name}")
            return []

    @property
    def current_option(self) -> str | None:
        # If we've set a current option explicitly and it's valid, prefer it
        if hasattr(self, "_attr_current_option") and self._attr_current_option in self.options:
            return self._attr_current_option

        if self.entity_description.current_selection is not None:
            try:
                state = self.entity_description.current_selection(self.device)
                # Only expose labels HA knows about
                return state if state in self.options else None
            except Exception as e:
                _LOGGER.error("current_selection callback failed for %s: %s", self.device.name, e)
                return None

        state = getattr(self.device, self.entity_description.key, None)
        if state is None:
            _LOGGER.warning("Current option '%s' is None for device %s", self.entity_description.key, self.device.name)
            return None
        _LOGGER.debug("Retrieved current option for '%s', %s: %s", self.entity_description.key, self.device.name, state)
        return state if state in self.options else None
    
    async def async_select_option(self, current_selection: str) -> None:
        _LOGGER.debug(f"Setting current option {current_selection} for {self.device.name}")
        try:
            _LOGGER.debug(f"Calling method with current option={current_selection} for {self.device.name}")
            await self.entity_description.method(self.device, current_selection)

            # Immediately reflect the user's choice if it's a valid option
            if current_selection in self.options:
                self._attr_current_option = current_selection
                self.async_write_ha_state()

            _LOGGER.debug(f"Current option {current_selection} set successfully for {self.device.name}")
        except Exception as e:
            _LOGGER.error(f"Error setting current option {current_selection} for {self.device.name}: {e}")

    @staticmethod
    def map_value_to_api(*, key: str, current_selection: str) -> str:
        """Map user-friendly values to API-compatible values."""
        mappings = {
            "lid_speed": {
                "Slow": "SLOW",
                "Medium": "MEDIUM",
                "Fast": "FAST"
            },
            "lid_mode": {
                "Open Mode (Stays Open Until Closed)": "KEEP_OPEN",
                "Personal Mode (Opens on Detection)": "CUSTOM"
            },
            "display_icon": {
                "Heart": 5,
                "Dog": 6,
                "Cat": 7,
                "Elk": 8,
            },
            "vacuum_mode": {
                "Study": "LEARNING",
                "Normal": "NORMAL",
                "Manual": "MANUAL"
            },
            "plate_position": {
                "Plate 1": 1,
                "Plate 2": 2,
                "Plate 3": 3,
            }
        }
        return mappings.get(key, {}).get(current_selection, "unknown")

DEVICE_SELECT_MAP: dict[type[Device], list[PetLibroSelectEntityDescription]] = {
    Feeder: [
    ],
    SpaceSmartFeeder: [
        PetLibroSelectEntityDescription[SpaceSmartFeeder](
            key="vacuum_mode",
            translation_key="vacuum_mode",
            icon="mdi:air-purifier",
            current_selection=lambda device: device.vacuum_mode,
            method=lambda device, current_selection: device.set_vacuum_mode(PetLibroSelectEntity.map_value_to_api(key="vacuum_mode", current_selection=current_selection)),
            options_list=['Study','Normal','Manual'],
            name="Vacuum Mode"
        ),
    ],
    OneRFIDSmartFeeder: [
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="lid_speed",
            translation_key="lid_speed",
            icon="mdi:speedometer",
            current_selection=lambda device: device.lid_speed,
            method=lambda device, current_selection: device.set_lid_speed(PetLibroSelectEntity.map_value_to_api(key="lid_speed", current_selection=current_selection)),
            options_list=['Slow','Medium','Fast'],
            name="Lid Speed"
        ),
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="lid_mode",
            translation_key="lid_mode",
            icon="mdi:arrow-oscillating",
            current_selection=lambda device: device.lid_mode,
            method=lambda device, current_selection: device.set_lid_mode(PetLibroSelectEntity.map_value_to_api(key="lid_mode", current_selection=current_selection)),
            options_list=['Open Mode (Stays Open Until Closed)','Personal Mode (Opens on Detection)'],
            name="Lid Mode"
        ),
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="display_icon",
            translation_key="display_icon",
            icon="mdi:monitor-star",
            current_selection=lambda device: device.display_icon,
            method=lambda device, current_selection: device.set_display_icon(PetLibroSelectEntity.map_value_to_api(key="display_icon", current_selection=current_selection)),
            options_list=['Heart','Dog','Cat','Elk'],
            name="Icon to Display"
        )
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroSelectEntityDescription[DockstreamSmartRFIDFountain](
            key="water_dispensing_mode",
            translation_key="water_dispensing_mode",
            icon="mdi:arrow-oscillating",
            current_selection=lambda device: device.water_dispensing_mode,
            method=lambda d, opt: (
                _apply_with_cached_schedule(d, lambda interval, duration, _off: d.api.set_water_mode_intermittent(d.serial, interval, duration)) if opt == "Intermittent Water (Scheduled)" 
                else
                _apply_with_cached_schedule(d, lambda interval, duration, _off: d.api.set_water_mode_constant(d.serial, interval, duration))
            ),
            options_list=['Flowing Water (Constant)','Intermittent Water (Scheduled)'],
            name="Water Dispensing Mode"
        ),
    ],
    Dockstream2SmartCordlessFountain: [
        PetLibroSelectEntityDescription[Dockstream2SmartCordlessFountain](
            key="water_dispensing_mode",
            translation_key="water_dispensing_mode",
            icon="mdi:arrow-oscillating",
            current_selection=lambda device: device.water_dispensing_mode,
            method=lambda d, opt: (
                _apply_and_refresh(d, d.api.set_water_mode_off(d.serial)) if opt == "Off" 
                else
                _apply_with_cached_schedule(d, lambda interval, duration, off: d.api.set_water_mode_radar_near(d.serial, interval, duration, currently_off=off)) if opt == "Sensor-Activated (Near)" 
                else
                _apply_with_cached_schedule(d, lambda interval, duration, off: d.api.set_water_mode_radar_far(d.serial, interval, duration, currently_off=off)) if opt == "Sensor-Activated (Far)" 
                else
                _apply_with_cached_schedule( d, lambda interval, duration, off: d.api.set_new_water_mode_constant(d.serial, interval, duration, currently_off=off))  # Flowing Water (Constant)
            ),
            options_list=['Flowing Water (Constant)','Sensor-Activated (Near)','Sensor-Activated (Far)','Off'],
            name="Water Dispensing Mode"
        ),
    ],
    Dockstream2SmartFountain: [
        PetLibroSelectEntityDescription[Dockstream2SmartFountain](
            key="water_dispensing_mode",
            translation_key="water_dispensing_mode",
            icon="mdi:arrow-oscillating",
            current_selection=lambda device: device.water_dispensing_mode,
            method=lambda d, opt: (
                _apply_and_refresh(d, d.api.set_water_mode_off(d.serial)) if opt == "Off" 
                else
                _apply_with_cached_schedule(d, lambda interval, duration, off: d.api.set_new_water_mode_intermittent(d.serial, interval, duration, currently_off=off)) if opt == "Intermittent Water (Scheduled)" 
                else
                _apply_with_cached_schedule(d, lambda interval, duration, off: d.api.set_new_water_mode_constant(d.serial, interval, duration, currently_off=off))
            ),
            options_list=['Flowing Water (Constant)','Intermittent Water (Scheduled)','Off'],
            name="Water Dispensing Mode"
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroSelectEntityDescription[DockstreamSmartFountain](
            key="water_dispensing_mode",
            translation_key="water_dispensing_mode",
            icon="mdi:arrow-oscillating",
            current_selection=lambda device: device.water_dispensing_mode,
            method=lambda d, opt: (
                _apply_with_cached_schedule(d, lambda interval, duration, _off: d.api.set_water_mode_intermittent(d.serial, interval, duration)) if opt == "Intermittent Water (Scheduled)" 
                else
                _apply_with_cached_schedule(d, lambda interval, duration, _off: d.api.set_water_mode_constant(d.serial, interval, duration))
            ),
            options_list=['Flowing Water (Constant)','Intermittent Water (Scheduled)'],
            name="Water Dispensing Mode"
        ),
    ],
    PolarWetFoodFeeder: [
        PetLibroSelectEntityDescription[PolarWetFoodFeeder](
            key="plate_position",
            translation_key="plate_position",
            icon="mdi:rotate-3d-variant",
            current_selection=lambda d: f"Plate {d.plate_position}" if d.plate_position else None,
            method=lambda d, opt: d.set_plate_position(int(opt.split()[-1])),
            options_list=["Plate 1", "Plate 2", "Plate 3"],
            name="Plate Position"
        ), 
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

