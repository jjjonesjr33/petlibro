"""Support for PETLIBRO selects."""
from __future__ import annotations
import math
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
from .const import DOMAIN, DEFAULT_PORTIONS_IN_CUP, Unit, APIKey, IntegrationSetting
from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.const import Platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary

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
from .devices.litterboxes.luma_smart_litter_box import LumaSmartLitterBox
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription
from .pets.entity import PL_PetSelectEntity


_LOGGER = logging.getLogger(__name__)


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
    method: Callable[[_DeviceT, str], Any] = field(default=lambda d,_: True)  # Default lambda function
    current_selection: Callable[[_DeviceT], str] | None = lambda _: None  # Default to None
    petlibro_unit: APIKey | str | None = None

class PetLibroSelectEntity(PetLibroEntity[_DeviceT], SelectEntity):
    """PETLIBRO select entity."""

    entity_description: PetLibroSelectEntityDescription[_DeviceT]

    def __init__(self, device, hub, description):
        """Initialize the select entity."""
        super().__init__(device, hub, description)

        if (unit_type := self.entity_description.petlibro_unit) and unit_type == APIKey.FEED_UNIT:
            self.hub.unit_entities.feed_number_unique_ids[Platform.SELECT].append(self._attr_unique_id)

    @property
    def options(self) -> list[str]:
        """Return the list of available options for the select."""    
        if self.key == "manual_feed_quantity_cups":
            return self.hub.unit_entities.cups_select_options(self.device)
        
        if not self.entity_description.options:
            # If there are no options, return an empty list and log an error.
            _LOGGER.error(f"No options available for select entity {self.name}")
            return []
        return super().options 

    @property
    def current_option(self) -> str | None:
        # If we've set a current option explicitly and it's valid, prefer it
        if hasattr(self, "_attr_current_option") and self._attr_current_option in self.options:
            return self._attr_current_option
        
        if self.key == "manual_feed_quantity_cups":
            return self.options[self.device.manual_feed_quantity - 1]

        if (current_selection := self.entity_description.current_selection(self.device)) is not None:
            try:
                # Only expose labels HA knows about
                return current_selection if current_selection in self.options else None
            except Exception as e:
                _LOGGER.error("current_selection callback failed for %s: %s", self.device.name, e)
                return None

        state = getattr(self.device, self.key, None)
        if state is None:
            _LOGGER.warning("Current option '%s' is None for device %s", self.key, self.device.name)
            return None
        _LOGGER.debug("Retrieved current option for '%s', %s: %s", self.key, self.device.name, state)
        return state if state in self.options else None

    async def async_select_option(self, current_selection: str) -> None:
        _LOGGER.debug(f"Setting current option {current_selection} for {self.device.name}")
        try:
            _LOGGER.debug(f"Calling method with current option={current_selection} for {self.device.name}")
            match self.key:
                case "manual_feed_quantity_cups":
                     await self.device.set_manual_feed_quantity(self.options.index(current_selection) + 1)
                case _:
                    if method := self.entity_description.method:
                        await method(self.device, current_selection)

            # Immediately reflect the user's choice if it's a valid option
            if current_selection in self.options:
                self._attr_current_option = current_selection
                self.async_write_ha_state()
            _LOGGER.debug(f"Current option {current_selection} set successfully for {self.device.name}")
        except Exception as e:
            _LOGGER.error(f"Error setting current option {current_selection} for {self.device.name}: {e}")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.key == "manual_feed_quantity_cups":
            return self.enable_for_manual_feed
        return super().available

    @property
    def entity_registry_visible_default(self) -> bool:
        """Return if the entity should be visible when first added."""
        if self.key == "manual_feed_quantity_cups":
            return self.enable_for_manual_feed
        return super().entity_registry_visible_default

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added."""
        if self.key == "manual_feed_quantity_cups":
            return self.enable_for_manual_feed
        return super().entity_registry_enabled_default

    @property
    def enable_for_manual_feed(self) -> bool:
        """Return True if entity should be enabled for manual feed portion setting."""
        return self.member.feedUnitType is Unit.CUPS and not self.hub.entry.options.get(
            IntegrationSetting.MANUAL_FEED_PORTIONS,
            IntegrationSetting.MANUAL_FEED_PORTIONS.default,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (self.entity_description.petlibro_unit == APIKey.FEED_UNIT
            and self.enabled != self.enable_for_manual_feed
        ):
            self.hub.unit_entities.schedule_manual_feed_sync()
            _LOGGER.warning("Feed unit mismatch, reloading integration.")

        if self.enabled:
            super()._handle_coordinator_update()

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


# ---------------------------------------------------------------------------
# Feeding plan select entities
# Used by feeding plan services to let the user pick a plan from a dropdown.
# Options are formatted as "Label - ID" (e.g. "MorningFeed - 3907147").
# Selecting an option stores the choice locally — no API call is made.
# The service handlers read the selected option to extract the plan ID.
# ---------------------------------------------------------------------------

class FeedingPlanSelectEntity(PetLibroEntity[_DeviceT], SelectEntity):
    """Base select entity for picking a feeding plan."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-clock"
    _attr_should_poll = False

    def __init__(self, device, hub, key: str, name: str) -> None:
        desc = PetLibroEntityDescription(key=key, name=name)
        super().__init__(device, hub, desc)
        self._attr_unique_id = f"{device.serial}-{key}"
        self._current: str | None = None

    def _build_options(self) -> list[str]:
        raise NotImplementedError

    @property
    def options(self) -> list[str]:
        return self._build_options()

    @property
    def current_option(self) -> str | None:
        opts = self.options
        if not opts:
            return None
        if self._current in opts:
            return self._current
        return opts[0]

    async def async_select_option(self, option: str) -> None:
        """User picked a plan — store locally, no API call."""
        self._current = option
        self.async_write_ha_state()


class FeedingScheduleSelectEntity(FeedingPlanSelectEntity[_DeviceT]):
    """Select listing ALL plans in the recurring schedule."""

    def _build_options(self) -> list[str]:
        plans = getattr(self.device, "feeding_plan_data", {})
        return [
            f"{plan.get('label') or f'plan_{pid}'} - {pid}"
            for pid, plan in plans.items()
        ] or ["No plans"]


class FeedingTodaySelectEntity(FeedingPlanSelectEntity[_DeviceT]):
    """Select listing only TODAY's feeding plan events."""

    def _build_options(self) -> list[str]:
        today = getattr(self.device, "feeding_plan_today_data", {}).get("plans", [])
        plan_data = getattr(self.device, "feeding_plan_data", {})
        opts = []
        for p in today:
            if not p.get("planId"):
                continue
            plan_id = p["planId"]
            label = plan_data.get(str(plan_id), {}).get("label") or f"plan_{p['index']}"
            opts.append(f"{label} - {plan_id}")
        return opts or ["No plans today"]


DEVICE_SELECT_MAP: dict[type[Device], list[PetLibroSelectEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
        PetLibroSelectEntityDescription[AirSmartFeeder](
            key="manual_feed_quantity_cups",
            translation_key="manual_feed_quantity_cups",
            icon="mdi:scale",
            unit_of_measurement=Unit.CUPS.symbol,
            name="Manual Feed Quantity",
            petlibro_unit=APIKey.FEED_UNIT
        )
    ],
    GranarySmartFeeder: [
        PetLibroSelectEntityDescription[GranarySmartFeeder](
            key="manual_feed_quantity_cups",
            translation_key="manual_feed_quantity_cups",
            icon="mdi:scale",
            unit_of_measurement=Unit.CUPS.symbol,
            name="Manual Feed Quantity",
            petlibro_unit=APIKey.FEED_UNIT
        )
    ],
    GranarySmartCameraFeeder: [
        PetLibroSelectEntityDescription[GranarySmartCameraFeeder](
            key="manual_feed_quantity_cups",
            translation_key="manual_feed_quantity_cups",
            icon="mdi:scale",
            unit_of_measurement=Unit.CUPS.symbol,
            name="Manual Feed Quantity",
            petlibro_unit=APIKey.FEED_UNIT
        )
    ],
    SpaceSmartFeeder: [
        PetLibroSelectEntityDescription[SpaceSmartFeeder](
            key="vacuum_mode",
            translation_key="vacuum_mode",
            icon="mdi:air-purifier",
            current_selection=lambda device: device.vacuum_mode,
            method=lambda device, current_selection: device.set_vacuum_mode(PetLibroSelectEntity.map_value_to_api(key="vacuum_mode", current_selection=current_selection)),
            options=['Study','Normal','Manual'],
            name="Vacuum Mode"
        ),
        PetLibroSelectEntityDescription[SpaceSmartFeeder](
            key="manual_feed_quantity_cups",
            translation_key="manual_feed_quantity_cups",
            icon="mdi:scale",
            unit_of_measurement=Unit.CUPS.symbol,
            name="Manual Feed Quantity",
            petlibro_unit=APIKey.FEED_UNIT
        )
    ],
    OneRFIDSmartFeeder: [
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="manual_feed_quantity_cups",
            translation_key="manual_feed_quantity_cups",
            icon="mdi:scale",
            unit_of_measurement=Unit.CUPS.symbol,
            name="Manual Feed Quantity",
            petlibro_unit=APIKey.FEED_UNIT
        ),
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="lid_speed",
            translation_key="lid_speed",
            icon="mdi:speedometer",
            current_selection=lambda device: device.lid_speed,
            method=lambda device, current_selection: device.set_lid_speed(PetLibroSelectEntity.map_value_to_api(key="lid_speed", current_selection=current_selection)),
            options=['Slow','Medium','Fast'],
            name="Lid Speed"
        ),
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="lid_mode",
            translation_key="lid_mode",
            icon="mdi:arrow-oscillating",
            current_selection=lambda device: device.lid_mode,
            method=lambda device, current_selection: device.set_lid_mode(PetLibroSelectEntity.map_value_to_api(key="lid_mode", current_selection=current_selection)),
            options=['Open Mode (Stays Open Until Closed)','Personal Mode (Opens on Detection)'],
            name="Lid Mode"
        ),
        PetLibroSelectEntityDescription[OneRFIDSmartFeeder](
            key="display_icon",
            translation_key="display_icon",
            icon="mdi:monitor-star",
            current_selection=lambda device: device.display_icon,
            method=lambda device, current_selection: device.set_display_icon(PetLibroSelectEntity.map_value_to_api(key="display_icon", current_selection=current_selection)),
            options=['Heart','Dog','Cat','Elk'],
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
            options=['Flowing Water (Constant)','Intermittent Water (Scheduled)'],
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
            options=['Flowing Water (Constant)','Sensor-Activated (Near)','Sensor-Activated (Far)','Off'],
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
            options=['Flowing Water (Constant)','Intermittent Water (Scheduled)','Off'],
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
            options=['Flowing Water (Constant)','Intermittent Water (Scheduled)'],
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
            options=["Plate 1", "Plate 2", "Plate 3"],
            name="Plate Position"
        ),
    ],
    LumaSmartLitterBox: [
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO select using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded
    if not (devices := hub.devices):
        _LOGGER.warning("No devices found in hub during select setup.")

    # Ensure that the pets are loaded
    if not (pets := hub.pets):
        _LOGGER.warning("No pets found in hub during select setup.")

    if not (devices or pets):
        return

    entities = []

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    if devices:
        # Devices should already be loaded in the hub
        _LOGGER.debug("Devices in hub: %s", devices)

        # Create select entities for each device based on the select map
        entities.extend(
            [
                PetLibroSelectEntity(device, hub, description)
                for device in devices.values()
                for device_type, entity_descriptions in DEVICE_SELECT_MAP.items()
                if isinstance(device, device_type)
                for description in entity_descriptions
            ]
        )

        # Add feeding plan select entities for dry feeders
        for device in devices.values():
            if hasattr(device, "feeding_plan_data"):
                entities.append(
                    FeedingScheduleSelectEntity(
                        device, hub, "feeding_plan_select", "Feeding Schedule"
                    )
                )
                entities.append(
                    FeedingTodaySelectEntity(
                        device, hub, "feeding_plan_today_select", "Today's Feeding Schedule"
                    )
                )

    if not entities:
        _LOGGER.warning("No select entities added, entities list is empty!")
    else:
        # Log the select of entities and their details
        _LOGGER.debug("Adding %d PetLibro select entities", len(entities))
        for entity in entities:
            _LOGGER.debug(
                "Adding select entity: %s for device %s",
                entity.entity_description.name,
                entity.device.name,
            )

    if pets:
        for pet in pets.values():
            entities.extend(pet.entities(PL_PetSelectEntity, hub))

    if entities:
        # Add select entities to Home Assistant
        async_add_entities(entities)