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
from .const import DOMAIN, Unit, APIKey as API, VALID_UNIT_TYPES
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .hub import PetLibroHub

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
from .devices.litterboxes.luma_smart_litter_box import LumaSmartLitterBox
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription


@dataclass(frozen=True)
class PetLibroBinarySensorEntityDescription(BinarySensorEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device binary sensor entities."""

    device_class_fn: Callable[[_DeviceT], BinarySensorDeviceClass | None] = lambda _: None
    should_report: Callable[[_DeviceT], bool] = lambda _: True
    device_class: Optional[BinarySensorDeviceClass] = None
    # Optional override for is_on — use when the entity key differs from the device property
    value_fn: Callable | None = None


class PetLibroBinarySensorEntity(PetLibroEntity[_DeviceT], BinarySensorEntity):
    """PETLIBRO binary sensor entity."""

    entity_description: PetLibroBinarySensorEntityDescription[_DeviceT]

    @cached_property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        return self.entity_description.device_class

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        if not self.entity_description.should_report(self.device):
            return False

        # Use value_fn override when the key doesn't match a device property directly
        if self.entity_description.value_fn is not None:
            return bool(self.entity_description.value_fn(self.device))

        state = getattr(self.device, self.entity_description.key, None)

        last_state = getattr(self, '_last_state', None)
        initial_log_done = getattr(self, '_initial_log_done', False)

        if not initial_log_done:
            self._initial_log_done = True
        elif last_state != state:
            if state:
                _LOGGER.info(f"Device {self.device.name} is online.")
            else:
                _LOGGER.warning(f"Device {self.device.name} is offline.")

        self._last_state = state
        return bool(state)

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        match self.key:
            case "feeding_plan_state":
                # Today's feeding plan events with formatted amounts
                today_data = getattr(self.device, "feeding_plan_today_data", {})
                plans = today_data.get("plans", []) if isinstance(today_data, dict) else []
                if not plans:
                    return {}
                plan_data = getattr(self.device, "feeding_plan_data", {})
                conv = getattr(self.device, "feed_conv_factor", 1)
                unit = self.member.feedUnitType
                weight = unit if unit in (Unit.GRAMS, Unit.OUNCES) else Unit.GRAMS
                volume = unit if unit in (Unit.MILLILITERS, Unit.CUPS) else Unit.MILLILITERS
                return {
                    plan_data.get(str(plan["planId"]), {}).get("label") or f"plan_{plan.get('index', plan['planId'])}": {
                        "time": plan.get("time"),
                        "amount (weight)": f"{Unit.convert_feed(plan.get('grainNum', 0) * conv, None, weight, True)} {weight.symbol}",
                        "amount (volume)": f"{Unit.convert_feed(plan.get('grainNum', 0) * conv, None, volume, True)} {volume.symbol}",
                        "state": {1: "Pending", 2: "Skipped", 3: "Completed", 4: "Skipped, Time Passed"}.get(plan.get("state"), "Unknown"),
                        "repeat": plan.get("repeat"),
                        "planID": plan.get("planId"),
                    }
                    for plan in plans
                } or {}
            case "feeding_schedule":
                # Full recurring schedule with formatted amounts
                plans = getattr(self.device, "feeding_plan_data", {})
                if not plans:
                    return {}
                conv = getattr(self.device, "feed_conv_factor", 1)
                unit = self.member.feedUnitType
                weight = unit if unit in (Unit.GRAMS, Unit.OUNCES) else Unit.GRAMS
                volume = unit if unit in (Unit.MILLILITERS, Unit.CUPS) else Unit.MILLILITERS
                return {
                    plan.get("label") or f"plan_{plan_id}": {
                        "planID": int(plan_id),
                        "time": plan.get("executionTime"),
                        "amount (weight)": f"{Unit.convert_feed(plan.get('grainNum', 0) * conv, None, weight, True)} {weight.symbol}",
                        "amount (volume)": f"{Unit.convert_feed(plan.get('grainNum', 0) * conv, None, volume, True)} {volume.symbol}",
                        "enabled": plan.get("enable", False),
                        "repeat_days": plan.get("repeatDay", "[]"),
                        "sound": plan.get("enableAudio", False),
                    }
                    for plan_id, plan in plans.items()
                } or {}
        return {}


DEVICE_BINARY_SENSOR_MAP: dict[type[Device], list[PetLibroBinarySensorEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="food_dispenser_state",
            translation_key="food_dispenser_state",
            icon="mdi:bowl-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_dispenser_state is not None,
            name="Food Dispenser"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
            name="Food Status"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            should_report=lambda device: device.enable_low_battery_notice is not None,
            name="Battery Status"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            should_report=lambda device: device.feeding_plan_state is not None,
            name="Today's Feeding Schedule"
        ),
        PetLibroBinarySensorEntityDescription[AirSmartFeeder](
            key="feeding_schedule",
            translation_key="feeding_schedule",
            icon="mdi:calendar-clock",
            should_report=lambda device: bool(getattr(device, "feeding_plan_data", {})),
            value_fn=lambda device: device.feeding_plan_state,
            name="Feeding Schedule"
        ),
    ],
    GranarySmartFeeder: [
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="food_dispenser_state",
            translation_key="food_dispenser_state",
            icon="mdi:bowl-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_dispenser_state is not None,
            name="Food Dispenser"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
            name="Food Status"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            should_report=lambda device: device.enable_low_battery_notice is not None,
            name="Battery Status"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            should_report=lambda device: device.feeding_plan_state is not None,
            name="Today's Feeding Schedule"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartFeeder](
            key="feeding_schedule",
            translation_key="feeding_schedule",
            icon="mdi:calendar-clock",
            should_report=lambda device: bool(getattr(device, "feeding_plan_data", {})),
            value_fn=lambda device: device.feeding_plan_state,
            name="Feeding Schedule"
        ),
    ],
    GranarySmartCameraFeeder: [
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="food_dispenser_state",
            translation_key="food_dispenser_state",
            icon="mdi:bowl-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_dispenser_state is not None,
            name="Food Dispenser"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
            name="Food Status"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            should_report=lambda device: device.enable_low_battery_notice is not None,
            name="Battery Status"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            should_report=lambda device: device.feeding_plan_state is not None,
            name="Today's Feeding Schedule"
        ),
        PetLibroBinarySensorEntityDescription[GranarySmartCameraFeeder](
            key="feeding_schedule",
            translation_key="feeding_schedule",
            icon="mdi:calendar-clock",
            should_report=lambda device: bool(getattr(device, "feeding_plan_data", {})),
            value_fn=lambda device: device.feeding_plan_state,
            name="Feeding Schedule"
        ),
    ],
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
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="sound_switch",
            translation_key="sound_switch",
            icon="mdi:volume-high",
            should_report=lambda device: device.sound_switch is not None,
            name="Sound Status"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            icon="mdi:lock",
            device_class=BinarySensorDeviceClass.LOCK,
            should_report=lambda device: device.child_lock_switch is not None,
            name="Buttons Lock"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="display_switch",
            translation_key="display_switch",
            icon="mdi:monitor-star",
            should_report=lambda device: device.display_switch is not None,
            name="Display Status"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            should_report=lambda device: device.feeding_plan_state is not None,
            name="Today's Feeding Schedule"
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="feeding_schedule",
            translation_key="feeding_schedule",
            icon="mdi:calendar-clock",
            should_report=lambda device: bool(getattr(device, "feeding_plan_data", {})),
            value_fn=lambda device: device.feeding_plan_state,
            name="Feeding Schedule"
        ),
    ],
    PolarWetFoodFeeder: [
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
            name="Food Status"
        ),
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            should_report=lambda device: device.enable_low_battery_notice is not None,
            name="Battery Status"
        ),
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="door_blocked",
            translation_key="door_blocked",
            icon="mdi:door-closed-lock",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.door_blocked is not None,
            name="Lid Status"
        ),
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[PolarWetFoodFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            should_report=lambda device: device.feeding_plan_state is not None,
            name="Feeding Plan"
        ),
    ],
    SpaceSmartFeeder: [
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="food_dispenser_state",
            translation_key="food_dispenser_state",
            icon="mdi:bowl-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_dispenser_state is not None,
            name="Food Dispenser"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="food_outlet_state",
            translation_key="food_outlet_state",
            icon="mdi:door",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_outlet_state is not None,
            name="Food Outlet"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="vacuum_state",
            translation_key="vacuum_state",
            icon="mdi:air-filter",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.vacuum_state is not None,
            name="Vacuum State"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
            name="Food Status"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,
            should_report=lambda device: device.enable_low_battery_notice is not None,
            name="Battery Status"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="sound_switch",
            translation_key="sound_switch",
            icon="mdi:volume-high",
            should_report=lambda device: device.sound_switch is not None,
            name="Sound Status"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            should_report=lambda device: device.feeding_plan_state is not None,
            name="Today's Feeding Schedule"
        ),
        PetLibroBinarySensorEntityDescription[SpaceSmartFeeder](
            key="feeding_schedule",
            translation_key="feeding_schedule",
            icon="mdi:calendar-clock",
            should_report=lambda device: bool(getattr(device, "feeding_plan_data", {})),
            value_fn=lambda device: device.feeding_plan_state,
            name="Feeding Schedule"
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroBinarySensorEntityDescription[DockstreamSmartFountain](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[DockstreamSmartFountain](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroBinarySensorEntityDescription[DockstreamSmartRFIDFountain](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[DockstreamSmartRFIDFountain](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
    ],
    Dockstream2SmartCordlessFountain: [
        PetLibroBinarySensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="power_state",
            translation_key="power_state",
            icon="mdi:power-plug",
            device_class=BinarySensorDeviceClass.PLUG,
            should_report=lambda device: device.power_state is not None,
            name="Power State"
        ),
        PetLibroBinarySensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="water_state",
            translation_key="water_state",
            icon="mdi:water",
            device_class=BinarySensorDeviceClass.MOISTURE,
            should_report=lambda device: device.water_state is not None,
            name="Water Dispensing State"
        ),
    ],
    Dockstream2SmartFountain: [
        PetLibroBinarySensorEntityDescription[Dockstream2SmartFountain](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[Dockstream2SmartFountain](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[Dockstream2SmartFountain](
            key="water_state",
            translation_key="water_state",
            icon="mdi:water",
            device_class=BinarySensorDeviceClass.MOISTURE,
            should_report=lambda device: device.water_state is not None,
            name="Water Dispensing State"
        ),
    ],
    LumaSmartLitterBox: [
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
            name="Wi-Fi"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="rubbish_full_state",
            translation_key="rubbish_full_state",
            icon="mdi:delete-alert",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.rubbish_full_state is not None,
            name="Waste Bin Full"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="rubbish_inplace_state",
            translation_key="rubbish_inplace_state",
            icon="mdi:delete-variant",
            device_class=BinarySensorDeviceClass.PRESENCE,
            should_report=lambda device: device.rubbish_inplace_state is not None,
            name="Waste Bin Installed"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="vacuum_state",
            translation_key="vacuum_state",
            icon="mdi:robot-vacuum",
            should_report=lambda device: device.vacuum_state is not None,
            name="Vacuum Active"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="deodorization_state_on",
            translation_key="deodorization_state_on",
            icon="mdi:air-purifier",
            should_report=lambda device: device.deodorization_state_on is not None,
            name="Deodorization Active"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="door_open",
            translation_key="door_open",
            icon="mdi:door-open",
            device_class=BinarySensorDeviceClass.DOOR,
            should_report=lambda device: device.door_open is not None,
            name="Door"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="device_stopped_working",
            translation_key="device_stopped_working",
            icon="mdi:alert-octagon",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.device_stopped_working is not None,
            name="Device Error"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            should_report=lambda device: device.light_switch is not None,
            name="Indicator"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            should_report=lambda device: device.whether_in_sleep_mode is not None,
            name="Sleep Mode"
        ),
        PetLibroBinarySensorEntityDescription[LumaSmartLitterBox](
            key="barn_door_error",
            translation_key="barn_door_error",
            icon="mdi:door-sliding-open",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.barn_door_error is not None,
            name="Door Error"
        ),
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO binary sensors using config entry."""
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    if not hub.devices:
        _LOGGER.warning("No devices found in hub during binary sensor setup.")
        return

    _LOGGER.debug("Hub data: %s", hub)
    devices = hub.devices
    _LOGGER.debug("Devices in hub: %s", devices)

    entities = [
        PetLibroBinarySensorEntity(device, hub, description)
        for device in devices.values()
        for device_type, entity_descriptions in DEVICE_BINARY_SENSOR_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No binary sensors added, entities list is empty!")
    else:
        _LOGGER.debug("Adding %d PetLibro binary sensors", len(entities))
        for entity in entities:
            _LOGGER.debug(
                "Adding binary sensor entity: %s for device %s",
                entity.entity_description.name,
                entity.device.name,
            )
        async_add_entities(entities)