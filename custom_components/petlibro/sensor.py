"""Support for PETLIBRO sensors."""
from __future__ import annotations
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from dataclasses import dataclass
from logging import getLogger
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast
from .const import DOMAIN
from homeassistant.components.sensor.const import SensorStateClass, SensorDeviceClass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary

_LOGGER = getLogger(__name__)

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

def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


def unit_of_measurement_feeder(device: Feeder) -> str | None:
    return device.unit_type


def device_class_feeder(device: Feeder) -> SensorDeviceClass | None:
    if device.unit_type in [UnitOfMass.OUNCES, UnitOfMass.GRAMS]:
        return SensorDeviceClass.WEIGHT
    if device.unit_type in [UnitOfVolume.MILLILITERS]:
        return SensorDeviceClass.VOLUME


@dataclass(frozen=True)
class PetLibroSensorEntityDescription(SensorEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    native_unit_of_measurement_fn: Callable[[_DeviceT], str | None] = lambda _: None
    device_class_fn: Callable[[_DeviceT], SensorDeviceClass | None] = lambda _: None
    should_report: Callable[[_DeviceT], bool] = lambda _: True


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
        
        # Dictionary to keep track of the last known state for each sensor key
        self._last_sensor_state = {}

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""

        sensor_key = self.entity_description.key
        
        # Handle feeding_plan_state as "On" or "Off"
        if sensor_key == "feeding_plan_state":
            feeding_plan_active = getattr(self.device, sensor_key, False)
            # Log only if the state has changed
            if self._last_sensor_state.get(sensor_key) != feeding_plan_active:
                _LOGGER.debug(f"Raw {sensor_key} for device {self.device.serial}: {feeding_plan_active}")
                self._last_sensor_state[sensor_key] = feeding_plan_active
            return "On" if feeding_plan_active else "Off"

        # Handle today_eating_time as raw seconds value
        elif sensor_key == "today_eating_time":
            eating_time_seconds = getattr(self.device, sensor_key, 0)
            return eating_time_seconds

        # Handle today_feeding_quantity as raw numeric value, converting to cups
        elif sensor_key == "today_feeding_quantity":
            feeding_quantity = getattr(self.device, sensor_key, 0)
            # Determine the conversion factor based on device-specific attributes or context
            conversion_factor = 1 / 12  # Default conversion factor
            if hasattr(self.device, "conversion_mode") and self.device.conversion_mode == "1/24":
                conversion_factor = 1 / 24
            
            cups = feeding_quantity * conversion_factor
            return f"{round(cups, 2)}"

        # Handle wifi_rssi to display only the numeric value
        elif sensor_key == "wifi_rssi":
            wifi_rssi = getattr(self.device, sensor_key, None)
            if wifi_rssi is not None:
                if self._last_sensor_state.get(sensor_key) != wifi_rssi:
                    _LOGGER.debug(f"Raw {sensor_key} for device {self.device.serial}: {wifi_rssi}")
                    self._last_sensor_state[sensor_key] = wifi_rssi
                return wifi_rssi

        # Handle weight in grams and convert to ounces
        elif sensor_key == "weight":
            weight_in_grams = getattr(self.device, sensor_key, 0.0)
            ounces = round(weight_in_grams * 0.035274, 2)
            return ounces

        # Default behavior for other sensors
        if self.entity_description.should_report(self.device):
            val = getattr(self.device, sensor_key, None)
            # Log only if the state has changed
            if self._last_sensor_state.get(sensor_key) != val:
                _LOGGER.debug(f"Raw {sensor_key} for device {self.device.serial}: {val}")
                self._last_sensor_state[sensor_key] = val
            return val
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement to use in the frontend, if any."""
        # For temperature, display as Fahrenheit
        if self.entity_description.key == "temperature":
            return "°F"
        # For today_feeding_quantity, display as cups in the frontend
        if self.entity_description.key == "today_feeding_quantity":
            return "cups"
        # For today_eating_time, display as seconds in the frontend
        elif self.entity_description.key == "today_eating_time":
            return "s"
        # For wifi_rssi, display as dBm
        elif self.entity_description.key == "wifi_rssi":
            return "dBm"
        # For weight, display as ounces in the frontend
        elif self.entity_description.key == "weight":
            return "oz"
        # For use_water_interval and use_water_duration, display as minutes
        elif self.entity_description.key in ["use_water_interval", "use_water_duration"]:
            return "min"
        # For weight_percent, display as a percentage
        elif self.entity_description.key == "weight_percent":
            return "%"
        # For electric_quantity, display as a percentage
        elif self.entity_description.key == "electric_quantity":
            return "%"
        # Default behavior for other sensors
        return self.entity_description.native_unit_of_measurement_fn(self.device)

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        if (device_class := self.entity_description.device_class_fn(self.device)) is not None:
            return device_class
        return super().device_class


DEVICE_SENSOR_MAP: dict[type[Device], list[PetLibroSensorEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="mac",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            key="today_feeding_quantity",
            translation_key="today_feeding_quantity",
            icon="mdi:scale",
            native_unit_of_measurement_fn=unit_of_measurement_feeder,
            device_class_fn=device_class_feeder,
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Quantity"
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
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
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="mac",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            key="today_feeding_quantity",
            translation_key="today_feeding_quantity",
            icon="mdi:scale",
            native_unit_of_measurement_fn=unit_of_measurement_feeder,
            device_class_fn=device_class_feeder,
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Quantity"
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
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
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="mac_address",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            native_unit_of_measurement="days",
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
            key="today_feeding_quantity",
            translation_key="today_feeding_quantity",
            icon="mdi:scale",
            native_unit_of_measurement_fn=unit_of_measurement_feeder,
            device_class_fn=device_class_feeder,
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Quantity"
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Times"
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
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="mac",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            key="today_feeding_quantity",
            translation_key="today_feeding_quantity",
            icon="mdi:scale",
            native_unit_of_measurement_fn=unit_of_measurement_feeder,
            device_class_fn=device_class_feeder,
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Feeding Quantity"
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
            native_unit_of_measurement="s",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            name="Today Eating Time"
        ),
    ],
    PolarWetFoodFeeder: [
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="mac",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            key="plate_position",
            translation_key="plate_position",
            icon="mdi:rotate-3d-variant",
            name="Plate Position",
            should_report=lambda device: device.plate_position is not None,
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="mac",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="weight",
            translation_key="weight",
            icon="mdi:scale",
            native_unit_of_measurement="oz",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:scale",
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
            native_unit_of_measurement="days",
            name="Remaining Filter Days"
        ),
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device SN"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="mac",
            translation_key="mac_address",
            icon="mdi:network",
            name="MAC Address"
        ),
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
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="weight",
            translation_key="weight",
            icon="mdi:scale",
            native_unit_of_measurement="oz",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:scale",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Current Weight Percent"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="use_water_interval",
            translation_key="use_water_interval",
            icon="mdi:water",
            native_unit_of_measurement="min",
            name="Water Interval"
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="use_water_duration",
            translation_key="use_water_duration",
            icon="mdi:water",
            native_unit_of_measurement="min",
            name="Water Time Duration"
        ),
# Does not work with multi pet tracking, but may use this code later once I have the API info for the RFID tags.
#        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
#            key="today_total_ml",
#            translation_key="today_total_ml",
#            icon="mdi:water",
#            native_unit_of_measurement="mL",
#            state_class=SensorStateClass.TOTAL_INCREASING,
#            name="Total Water Used Today"
#        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="remaining_filter_days",
            translation_key="remaining_filter_days",
            icon="mdi:package",
            native_unit_of_measurement="days",
            name="Remaining Filter Days"
        ),
    ]
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

    # Ensure that the devices are loaded
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during sensor setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create sensor entities for each device based on the sensor map
    entities = [
        PetLibroSensorEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_SENSOR_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No sensors added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro sensors", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding sensor entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add sensor entities to Home Assistant
        async_add_entities(entities)

