"""Support for PETLIBRO sensors."""
from __future__ import annotations
from dataclasses import dataclass
from logging import getLogger
from collections.abc import Callable
from datetime import datetime
from .const import DOMAIN, VALID_UNIT_TYPES, Unit, APIKey as API
from homeassistant.components.sensor.const import SensorStateClass, SensorDeviceClass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfMass, UnitOfVolume, UnitOfTime, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import VolumeConverter
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary
from .member import MemberEntity

_LOGGER = getLogger(__name__)

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

def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


@dataclass(frozen=True)
class PetLibroSensorEntityDescription(SensorEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device sensor entities."""
    should_report: Callable[[_DeviceT], bool] = lambda _: True
    petlibro_unit: API | str | None = None


class PetLibroSensorEntity(PetLibroEntity[_DeviceT], SensorEntity):
    """PETLIBRO sensor entity."""
    entity_description: PetLibroSensorEntityDescription[_DeviceT]

    def __init__(self, device, hub, description):
        """Initialize the sensor."""
        super().__init__(device, hub, description)
        
        # Ensure unique_id includes the device serial, specific sensor key, and the MAC address from the device attributes
        mac_address = getattr(device, "mac", None)
        if mac_address:
            self._attr_unique_id = f"{device.serial}-{description.key}-{mac_address.replace(':', '')}"
        else:
            self._attr_unique_id = f"{device.serial}-{description.key}"
        
        if unit_type := self.entity_description.petlibro_unit:
            device_class = self.entity_description.device_class
            self.hub.unit_sensor_unique_ids[unit_type][device_class].append(self._attr_unique_id)
        
        # Dictionary to keep track of the last known state for each sensor key
        self._last_sensor_state = {}

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""        
        match self.key:
            case "feeding_plan_state":
                # Handle feeding_plan_state as "On" or "Off"
                feeding_plan_active = getattr(self.device, self.key, False)
                # Log only if the state has changed
                if self._last_sensor_state.get(self.key) != feeding_plan_active:
                    _LOGGER.debug(f"Raw {self.key} for device {self.device.serial}: {feeding_plan_active}")
                    self._last_sensor_state[self.key] = feeding_plan_active
                return "On" if feeding_plan_active else "Off"
            case "today_eating_time":
                # Handle today_eating_time as raw seconds value
                eating_time_seconds = getattr(self.device, self.key, 0)
                return eating_time_seconds
            case "today_drinking_time":
                # Handle today_drinking_time as raw seconds value
                drinking_time_seconds = getattr(self.device, self.key, 0)
                return drinking_time_seconds
            case "today_avg_time":
                today_avg_time_seconds = getattr(self.device, self.key, 0)
                return today_avg_time_seconds
            case "yesterday_drinking_time":
                # Handle yesterday_drinking_time as raw seconds value
                yesterday_drinking_time_seconds = getattr(self.device, self.key, 0)
                return yesterday_drinking_time_seconds
            case "wifi_rssi":
                # Handle wifi_rssi to display only the numeric value
                wifi_rssi = getattr(self.device, self.key, None)
                if wifi_rssi is not None:
                    if self._last_sensor_state.get(self.key) != wifi_rssi:
                        _LOGGER.debug(f"Raw {self.key} for device {self.device.serial}: {wifi_rssi}")
                        self._last_sensor_state[self.key] = wifi_rssi
                    return wifi_rssi
            case "remaining_water":
                return self.device.weight
            case key if key in (
                "today_feeding_quantity_weight",
                "last_feed_quantity_weight",
                "next_feed_quantity_weight"
            ):
                return Unit.convert_feed(
                    getattr(self.device, key.removesuffix("_weight"), 0) * self.device.feed_conv_factor, 
                    None, Unit.GRAMS, True)
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume"
            ):
                return Unit.convert_feed(
                    getattr(self.device, key.removesuffix("_volume"), 0) * self.device.feed_conv_factor, 
                    None, Unit.MILLILITERS, True)
            case _:
                # Default behavior for other sensors
                if self.entity_description.should_report(self.device):
                    val = getattr(self.device, self.key, None)
                    # Log only if the state has changed
                    if self._last_sensor_state.get(self.key) != val:
                        _LOGGER.debug(f"Raw {self.key} for device {self.device.serial}: {val}")
                        self._last_sensor_state[self.key] = val
                    return val
        return super().native_value

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        return super().icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement to use in the frontend, if any."""
        match self.key:
            case "temperature":
                # For temperature, display as Fahrenheit
                return "°F"
            case key if key in (
                "today_eating_time", 
                "today_drinking_time", 
                "today_avg_time"
            ):
                # For today_eating_time, display as seconds in the frontend
                return UnitOfTime.SECONDS
            case key if key in (
                "remaining_cleaning_days", 
                "remaining_filter_days", 
                "remaining_desiccant"
            ):
                # For remaining_desiccant, remaining_cleaning_days & remaining_filter_days, display as days in the frontend
                return UnitOfTime.DAYS
            case "wifi_rssi":
                # For wifi_rssi, display as dBm
                return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
            case key if key in (
                "use_water_interval", 
                "use_water_duration"
            ):
                # For use_water_interval and use_water_duration, display as minutes
                return UnitOfTime.MINUTES
            case key if key in (
                "weight_percent", 
                "electric_quantity"
            ):
                # For weight_percent, display as a percentage
                return PERCENTAGE
            case key if key in (
                "remaining_water", 
                "today_drinking_amount", 
                "yesterday_drinking_amount"
            ):
                return UnitOfVolume.MILLILITERS
            case key if key in (
                "today_feeding_quantity_weight",
                "last_feed_quantity_weight",
                "next_feed_quantity_weight"
            ):
                return UnitOfMass.GRAMS
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume"
            ):
                return UnitOfVolume.MILLILITERS
        return super().native_unit_of_measurement

    @property
    def suggested_unit_of_measurement(self) -> int | None:
        """Return the suggested unit of measurement."""
        match self.key:
            case key if key in (
                "today_feeding_quantity_weight",
                "last_feed_quantity_weight",
                "next_feed_quantity_weight"
            ):
                return getattr(UnitOfMass, self.member.feedUnitType.name, None)
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume"
            ):
                return getattr(UnitOfVolume, self.member.feedUnitType.name, None)
            case key if key in (
                "remaining_water", 
                "today_drinking_amount", 
                "yesterday_drinking_amount"
            ):
                return self.member.waterUnitType.symbol
        return super().suggested_unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        return super().device_class

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""        
        match self.key:
            case "feeding_plan_state":
                plans = self.device.feeding_plan_today_data.get("plans", [])
                unit = self.member.feedUnitType
                weight = unit if unit in (Unit.GRAMS, Unit.OUNCES) else Unit.GRAMS
                volume = unit if unit in (Unit.MILLILITERS, Unit.CUPS) else Unit.MILLILITERS           
                return {
                    self.device.feeding_plan_data.get(str(plan["planId"]), {}).get("label") or f"plan_{plan['index']}": {
                        "time": plan["time"],
                        "amount (weight)": f"{Unit.convert_feed(plan['grainNum'] * self.device.feed_conv_factor, None, weight, True)} {weight.symbol}",
                        "amount (volume)": f"{Unit.convert_feed(plan['grainNum'] * self.device.feed_conv_factor, None, volume, True)} {volume.symbol}",
                        "state": {1: "Pending", 2: "Skipped", 3: "Completed", 4: "Skipped, Time Passed"}.get(plan["state"], "Unknown"),
                        "repeat": plan["repeat"],
                        "planID": plan["planId"]
                    }
                    for plan in plans
                }
            case "next_feed_time":
                next_feed = self.device.get_next_feed
                next_feed_data = self.device.feeding_plan_data.get(str(next_feed.get("id")), {})
                if next_feed_data:
                    return {
                        "label": next_feed_data.get("label"),
                        "id": next_feed_data.get("id"),
                        "meal_call": next_feed_data.get("enableAudio"),
                    }
            case key if key in (
                "today_feeding_quantity_weight",
                "last_feed_quantity_weight", 
                "next_feed_quantity_weight",
            ):
                portion = getattr(self.device, key.removesuffix("_weight"), 0)
                return {
                    unit.symbol: Unit.convert_feed(portion * self.device.feed_conv_factor, None, unit, True)
                    for unit in (Unit.GRAMS, Unit.OUNCES)
                }
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume"
            ):
                portion = getattr(self.device, key.removesuffix("_volume"), 0)
                return {
                    unit.symbol: Unit.convert_feed(portion * self.device.feed_conv_factor, None, unit, True)
                    for unit in (Unit.CUPS, Unit.MILLILITERS)
                }
            case key if key in (
                "remaining_water", 
                "today_drinking_amount", 
                "yesterday_drinking_amount"
            ):
                key = "weight" if key == "remaining_water" else key
                return { 
                    unit.symbol: VolumeConverter.convert(getattr(self.device, key, 0), UnitOfVolume.MILLILITERS, unit.symbol)
                    for unit in VALID_UNIT_TYPES[API.WATER_UNIT] if unit
                }                
        return super().extra_state_attributes

DEVICE_SENSOR_MAP: dict[type[Device], list[PetLibroSensorEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            name="Feeding Plan State",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="today_feeding_quantity_weight",
            translation_key="today_feeding_quantity_weight",
            name="Today Feeding Quantity (Weight)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="today_feeding_quantity_volume",
            translation_key="today_feeding_quantity_volume",
            name="Today Feeding Quantity (Volume)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="last_feed_time",
            translation_key="last_feed_time",
            icon="mdi:history",
            name="Last Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="last_feed_quantity_weight",
            translation_key="last_feed_quantity_weight",
            name="Last Feed Quantity (Weight)",
            icon="mdi:history",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="last_feed_quantity_volume",
            translation_key="last_feed_quantity_volume",
            name="Last Feed Quantity (Volume)",
            icon="mdi:history",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="next_feed_time",
            translation_key="next_feed_time",
            icon="mdi:calendar-arrow-right",
            name="Next Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            name="Next Feed Quantity (Weight)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="next_feed_quantity_volume",
            translation_key="next_feed_quantity_volume",
            name="Next Feed Quantity (Volume)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            icon="mdi:lock",
            name="Buttons Lock"
        ),
    ],
    GranarySmartFeeder: [
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Desiccant Days"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            name="Feeding Plan State",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="today_feeding_quantity_weight",
            translation_key="today_feeding_quantity_weight",
            name="Today Feeding Quantity (Weight)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="today_feeding_quantity_volume",
            translation_key="today_feeding_quantity_volume",
            name="Today Feeding Quantity (Volume)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="last_feed_time",
            translation_key="last_feed_time",
            icon="mdi:history",
            name="Last Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="last_feed_quantity_weight",
            translation_key="last_feed_quantity_weight",
            name="Last Feed Quantity (Weight)",
            icon="mdi:history",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="last_feed_quantity_volume",
            translation_key="last_feed_quantity_volume",
            name="Last Feed Quantity (Volume)",
            icon="mdi:history",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="next_feed_time",
            translation_key="next_feed_time",
            icon="mdi:calendar-arrow-right",
            name="Next Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            name="Next Feed Quantity (Weight)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="next_feed_quantity_volume",
            translation_key="next_feed_quantity_volume",
            name="Next Feed Quantity (Volume)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            icon="mdi:lock",
            name="Buttons Lock"
        ),
    ],
    GranarySmartCameraFeeder: [
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Desiccant Days"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            name="Feeding Plan State",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="today_feeding_quantity_weight",
            translation_key="today_feeding_quantity_weight",
            name="Today Feeding Quantity (Weight)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="today_feeding_quantity_volume",
            translation_key="today_feeding_quantity_volume",
            name="Today Feeding Quantity (Volume)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="last_feed_time",
            translation_key="last_feed_time",
            icon="mdi:history",
            name="Last Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="last_feed_quantity_weight",
            translation_key="last_feed_quantity_weight",
            name="Last Feed Quantity (Weight)",
            icon="mdi:history",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="last_feed_quantity_volume",
            translation_key="last_feed_quantity_volume",
            name="Last Feed Quantity (Volume)",
            icon="mdi:history",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="next_feed_time",
            translation_key="next_feed_time",
            icon="mdi:calendar-arrow-right",
            name="Next Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            name="Next Feed Quantity (Weight)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="next_feed_quantity_volume",
            translation_key="next_feed_quantity_volume",
            name="Next Feed Quantity (Volume)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            icon="mdi:lock",
            name="Buttons Lock"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="resolution",
            translation_key="resolution",
            icon="mdi:camera",
            name="Camera Resolution",
            should_report=lambda device: device.resolution is not None
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="night_vision",
            translation_key="night_vision",
            icon="mdi:weather-night",
            name="Night Vision Mode",
            should_report=lambda device: device.night_vision is not None  # Corrected name
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="enable_video_record",
            translation_key="enable_video_record",
            icon="mdi:video",
            name="Video Recording Enabled",
            should_report=lambda device: device.enable_video_record is not None  # Corrected name
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="video_record_switch",
            translation_key="video_record_switch",
            icon="mdi:video-outline",
            name="Video Recording Switch",
            should_report=lambda device: device.video_record_switch is not None  # Corrected name
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="video_record_mode",
            translation_key="video_record_mode",
            icon="mdi:motion-sensor",
            name="Video Recording Mode",
            should_report=lambda device: device.video_record_mode is not None  # Corrected name
        ),
    ],
    OneRFIDSmartFeeder: [
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Desiccant Days"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            name="Feeding Plan State",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_feeding_quantity_weight",
            translation_key="today_feeding_quantity_weight",
            name="Today Feeding Quantity (Weight)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_feeding_quantity_volume",
            translation_key="today_feeding_quantity_volume",
            name="Today Feeding Quantity (Volume)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_eating_times",
            translation_key="today_eating_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Eating Times"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_eating_time",
            translation_key="today_eating_time",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today's Total Eating Time"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="last_feed_time",
            translation_key="last_feed_time",
            icon="mdi:history",
            name="Last Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="last_feed_quantity_weight",
            translation_key="last_feed_quantity_weight",
            name="Last Feed Quantity (Weight)",
            icon="mdi:history",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="last_feed_quantity_volume",
            translation_key="last_feed_quantity_volume",
            name="Last Feed Quantity (Volume)",
            icon="mdi:history",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="next_feed_time",
            translation_key="next_feed_time",
            icon="mdi:calendar-arrow-right",
            name="Next Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            name="Next Feed Quantity (Weight)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="next_feed_quantity_volume",
            translation_key="next_feed_quantity_volume",
            name="Next Feed Quantity (Volume)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="display_selection",
            translation_key="display_selection",
            icon="mdi:monitor-shimmer",
            name="Display Value"
        ),
    ],
    PolarWetFoodFeeder: [
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan",
            icon="mdi:calendar-check",
            name="Feeding Plan",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="next_feeding_day",
            translation_key="next_feeding_day",
            icon="mdi:calendar-clock",
            name="Feeding Schedule"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="next_feeding_time",
            translation_key="next_feeding_time",
            icon="mdi:clock-outline",
            name="Feeding Begins"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="next_feeding_end_time",
            translation_key="next_feeding_end_time",
            icon="mdi:clock-end",
            name="Feeding Ends"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="temperature",
            translation_key="temperature",
            icon="mdi:thermometer",
            native_unit_of_measurement="°F",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            name="Temperature"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="plate_position",
            translation_key="plate_position",
            icon="mdi:rotate-3d-variant",
            name="Plate Position",
            should_report=lambda device: device.plate_position is not None,
        ),
    ],
    SpaceSmartFeeder: [
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            icon="mdi:calendar-check",
            name="Feeding Plan State",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="today_feeding_quantity_weight",
            translation_key="today_feeding_quantity_weight",
            name="Today Feeding Quantity (Weight)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="today_feeding_quantity_volume",
            translation_key="today_feeding_quantity_volume",
            name="Today Feeding Quantity (Volume)",
            icon="mdi:scale",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="last_feed_time",
            translation_key="last_feed_time",
            icon="mdi:history",
            name="Last Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="last_feed_quantity_weight",
            translation_key="last_feed_quantity_weight",
            name="Last Feed Quantity (Weight)",
            icon="mdi:history",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="last_feed_quantity_volume",
            translation_key="last_feed_quantity_volume",
            name="Last Feed Quantity (Volume)",
            icon="mdi:history",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="next_feed_time",
            translation_key="next_feed_time",
            icon="mdi:calendar-arrow-right",
            name="Next Feed Time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            name="Next Feed Quantity (Weight)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="next_feed_quantity_volume",
            translation_key="next_feed_quantity_volume",
            name="Next Feed Quantity (Volume)",
            icon="mdi:calendar-arrow-right",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="pump_air_state",
            translation_key="pump_air_state",
            icon="mdi:air-filter",
            name="Pump Air State"
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="vacuum_mode",
            translation_key="vacuum_mode",
            icon="mdi:air-filter",
            name="Vacuum Mode"
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="remaining_cleaning_days",
            translation_key="remaining_cleaning_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="remaining_water",
            translation_key="remaining_water",
            name="Remaining Water Volume",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL,
            device_class=SensorDeviceClass.VOLUME,
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_drinking_amount",
            translation_key="today_drinking_amount",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.VOLUME,
            name="Today's Water Consumption",
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="yesterday_drinking_amount",
            translation_key="yesterday_drinking_amount",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.VOLUME,
            name="Yesterday's Water Consumption",
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_drinking_time",
            translation_key="today_drinking_time",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today's Total Drinking Time"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_avg_time",
            translation_key="today_avg_time",
            icon="mdi:history",
            state_class=SensorStateClass.MEASUREMENT,
            name="Today's Average Drinking Time"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_drinking_count",
            translation_key="today_drinking_count",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Drinking Times"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="yesterday_drinking_count",
            translation_key="yesterday_drinking_count",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Yesterday Drinking Times"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:water-percent",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight Percent"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="use_water_interval",
            translation_key="use_water_interval",
            icon="mdi:water",
            native_unit_of_measurement="min",
            name="Water Interval"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="use_water_duration",
            translation_key="use_water_duration",
            icon="mdi:water",
            native_unit_of_measurement="min",
            name="Water Time Duration"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="remaining_filter_days",
            translation_key="remaining_filter_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Filter Days"
        ),
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="remaining_cleaning_days",
            translation_key="remaining_cleaning_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="remaining_water",
            translation_key="remaining_water",
            name="Remaining Water Volume",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL,
            device_class=SensorDeviceClass.VOLUME,
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:water-percent",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight Percent"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="use_water_interval",
            translation_key="use_water_interval",
            icon="mdi:water",
            native_unit_of_measurement="min",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Water Interval"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="use_water_duration",
            translation_key="use_water_duration",
            icon="mdi:water",
            native_unit_of_measurement="min",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Water Time Duration"
        ),
# Does not work with multi pet tracking, but may use this code later once I have the API info for the RFID tags.
#        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
#            key="today_drinking_amount",
#            translation_key="today_drinking_amount",
#            icon="mdi:water",
#            state_class=SensorStateClass.TOTAL_INCREASING,
#            device_class=SensorDeviceClass.VOLUME,
#            name="Total Water Used Today",
#            petlibro_unit=API.WATER_UNIT
#        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="remaining_filter_days",
            translation_key="remaining_filter_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Filter Days"
        ),
    ],
    Dockstream2SmartCordlessFountain: [
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="remaining_cleaning_days",
            translation_key="remaining_cleaning_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="remaining_water",
            translation_key="remaining_water",
            name="Remaining Water Volume",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL,
            device_class=SensorDeviceClass.VOLUME,
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:water-percent",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight Percent"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_drinking_amount",
            translation_key="today_drinking_amount",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.VOLUME,
            name="Today's Water Consumption",
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="yesterday_drinking_amount",
            translation_key="yesterday_drinking_amount",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.VOLUME,
            name="Yesterday's Water Consumption",
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="remaining_filter_days",
            translation_key="remaining_filter_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Filter Days"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="battery_charge_state",
            translation_key="battery_charge_state",
            icon="mdi:battery",
            name="Battery Status"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_drinking_time",
            translation_key="today_drinking_time",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today's Total Drinking Time"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_avg_time",
            translation_key="today_avg_time",
            icon="mdi:history",
            state_class=SensorStateClass.MEASUREMENT,
            name="Today's Average Drinking Time"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_drinking_count",
            translation_key="today_drinking_count",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Drinking Times"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="yesterday_drinking_count",
            translation_key="yesterday_drinking_count",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Yesterday Drinking Times"
        ),
    ],
    Dockstream2SmartFountain: [
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="remaining_cleaning_days",
            translation_key="remaining_cleaning_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="remaining_water",
            translation_key="remaining_water",
            name="Remaining Water Volume",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL,
            device_class=SensorDeviceClass.VOLUME,
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:water-percent",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight Percent"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_drinking_amount",
            translation_key="today_drinking_amount",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.VOLUME,
            name="Today's Water Consumption",
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="yesterday_drinking_amount",
            translation_key="yesterday_drinking_amount",
            icon="mdi:water",
            state_class=SensorStateClass.TOTAL_INCREASING,
            device_class=SensorDeviceClass.VOLUME,
            name="Yesterday's Water Consumption",
            petlibro_unit=API.WATER_UNIT
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="remaining_filter_days",
            translation_key="remaining_filter_days",
            icon="mdi:package",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Filter Days"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_drinking_time",
            translation_key="today_drinking_time",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today's Total Drinking Time"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_avg_time",
            translation_key="today_avg_time",
            icon="mdi:history",
            state_class=SensorStateClass.MEASUREMENT,
            name="Today's Average Drinking Time"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_drinking_count",
            translation_key="today_drinking_count",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Drinking Times"
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="yesterday_drinking_count",
            translation_key="yesterday_drinking_count",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Yesterday Drinking Times"
        ),
    ],
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO sensors using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the member is loaded
    if not (member := hub.member):
        _LOGGER.warning("No member found in hub during sensor setup.")

    # Ensure that the devices are loaded
    if not (devices := hub.devices):
        _LOGGER.warning("No devices found in hub during sensor setup.")

    if not (devices or member):
        return

    entities = []

    if devices:
        # Log the contents of the hub data for debugging
        _LOGGER.debug("Hub data: %s", hub)

        # Devices should already be loaded in the hub
        _LOGGER.debug("Devices in hub: %s", devices)

        # Create sensor entities for each device based on the sensor map
        entities.extend(
            [
                PetLibroSensorEntity(device, hub, description)
                for device in devices  # Iterate through devices from the hub
                for device_type, entity_descriptions in DEVICE_SENSOR_MAP.items()
                if isinstance(device, device_type)
                for description in entity_descriptions
            ]
        )

    if not entities:
        _LOGGER.warning("No device sensors added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro sensors", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding sensor entity: %s for device %s", entity.entity_description.name, entity.device.name)

    # Create Member sensor entity for front-end use.
    if member:
        entities.append(MemberEntity(member))
        _LOGGER.debug("Adding sensor entity for Petlibro member: %s", member.email)

    if entities:
        # Add sensor entities to Home Assistant
        async_add_entities(entities)

