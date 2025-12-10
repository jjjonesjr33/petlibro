"""Support for PETLIBRO sensors."""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.util.unit_conversion import VolumeConverter

from .const import DOMAIN, VALID_UNIT_TYPES, Unit
from .const import APIKey as API
from .devices import Device
from .devices.feeders.air_smart_feeder import AirSmartFeeder
from .devices.feeders.dry_food_feeder import DryFoodFeeder
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
from .devices.fountains.fountain import Fountain
from .entity import PetLibroEntity, PetLibroEntityDescription, _DeviceT
from .member import MemberEntity

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .hub import PetLibroHub

_LOGGER = getLogger(__name__)


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
class PetLibroSensorEntityDescription(
    SensorEntityDescription, PetLibroEntityDescription[_DeviceT]
):
    """A class that describes device sensor entities."""

    should_report: Callable[[_DeviceT], bool] = lambda _: True
    petlibro_unit: API | str | None = None


class PetLibroSensorEntity(PetLibroEntity[_DeviceT], SensorEntity):
    """PETLIBRO sensor entity."""

    entity_description: PetLibroSensorEntityDescription[_DeviceT]

    def __init__(
        self,
        device: _DeviceT,
        hub: PetLibroHub,
        description: PetLibroSensorEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, hub, description)

        # Ensure unique_id includes the device serial, specific sensor key, and the MAC address from the device attributes
        mac_address = getattr(device, "mac", None)
        if mac_address:
            self._attr_unique_id = (
                f"{device.serial}-{description.key}-{mac_address.replace(':', '')}"
            )
        else:
            self._attr_unique_id = f"{device.serial}-{description.key}"

        if unit_type := self.entity_description.petlibro_unit:
            device_class = self.entity_description.device_class
            self.hub.unit_sensor_unique_ids[unit_type][device_class].append(
                self._attr_unique_id
            )

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
                    _LOGGER.debug(
                        "Raw %s for device %s: %s",
                        self.key,
                        self.device.serial,
                        feeding_plan_active,
                    )
                    self._last_sensor_state[self.key] = feeding_plan_active
                return "On" if feeding_plan_active else "Off"
            case "today_eating_time":
                # Handle today_eating_time as raw seconds value
                return getattr(self.device, self.key, 0)
            case "today_drinking_time":
                # Handle today_drinking_time as raw seconds value
                return getattr(self.device, self.key, 0)
            case "today_avg_time":
                return getattr(self.device, self.key, 0)
            case "yesterday_drinking_time":
                # Handle yesterday_drinking_time as raw seconds value
                return getattr(self.device, self.key, 0)
            case "wifi_rssi":
                # Handle wifi_rssi to display only the numeric value
                wifi_rssi = getattr(self.device, self.key, None)
                if wifi_rssi is not None:
                    if self._last_sensor_state.get(self.key) != wifi_rssi:
                        _LOGGER.debug(
                            "Raw %s for device %s: %s",
                            self.key,
                            self.device.serial,
                            wifi_rssi,
                        )
                        self._last_sensor_state[self.key] = wifi_rssi
                    return wifi_rssi
            case "remaining_water":
                return self.device.weight
            case key if key in (
                "today_feeding_quantity_weight",
                "last_feed_quantity_weight",
                "next_feed_quantity_weight",
            ):
                return Unit.convert_feed(
                    getattr(self.device, key.removesuffix("_weight"), 0)
                    * self.device.feed_conv_factor,
                    None,
                    Unit.GRAMS,
                    True,
                )
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume",
            ):
                return Unit.convert_feed(
                    getattr(self.device, key.removesuffix("_volume"), 0)
                    * self.device.feed_conv_factor,
                    None,
                    Unit.MILLILITERS,
                    True,
                )
            case _:
                # Default behavior for other sensors
                if self.entity_description.should_report(self.device):
                    val = getattr(self.device, self.key, None)
                    # Log only if the state has changed
                    if self._last_sensor_state.get(self.key) != val:
                        _LOGGER.debug(
                            "Raw %s for device %s: %s",
                            self.key,
                            self.device.serial,
                            val,
                        )
                        self._last_sensor_state[self.key] = val
                    return val
        return super().native_value

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
                "today_avg_time",
            ):
                # For today_eating_time, display as seconds in the frontend
                return UnitOfTime.SECONDS
            case key if key in (
                "remaining_cleaning_days",
                "remaining_filter_days",
                "remaining_desiccant",
            ):
                # For remaining_desiccant, remaining_cleaning_days & remaining_filter_days, display as days in the frontend
                return UnitOfTime.DAYS
            case "wifi_rssi":
                # For wifi_rssi, display as dBm
                return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
            case key if key in ("use_water_interval", "use_water_duration"):
                # For use_water_interval and use_water_duration, display as minutes
                return UnitOfTime.MINUTES
            case key if key in ("weight_percent", "electric_quantity"):
                # For weight_percent, display as a percentage
                return PERCENTAGE
            case key if key in (
                "remaining_water",
                "today_drinking_amount",
                "yesterday_drinking_amount",
            ):
                return UnitOfVolume.MILLILITERS
            case key if key in (
                "today_feeding_quantity_weight",
                "last_feed_quantity_weight",
                "next_feed_quantity_weight",
            ):
                return UnitOfMass.GRAMS
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume",
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
                "next_feed_quantity_weight",
            ):
                return getattr(UnitOfMass, self.member.feedUnitType.name, None)
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume",
            ):
                return getattr(UnitOfVolume, self.member.feedUnitType.name, None)
            case key if key in (
                "remaining_water",
                "today_drinking_amount",
                "yesterday_drinking_amount",
            ):
                return self.member.waterUnitType.symbol
        return super().suggested_unit_of_measurement

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        match self.key:
            case "feeding_plan_state":
                plans = self.device.feeding_plan_today_data.get("plans", [])
                unit = self.member.feedUnitType
                weight = unit if unit in (Unit.GRAMS, Unit.OUNCES) else Unit.GRAMS
                volume = (
                    unit if unit in (Unit.MILLILITERS, Unit.CUPS) else Unit.MILLILITERS
                )
                return {
                    self.device.feeding_plan_data.get(str(plan["planId"]), {}).get(
                        "label"
                    )
                    or f"plan_{plan['index']}": {
                        "time": plan["time"],
                        "amount (weight)": f"{Unit.convert_feed(plan['grainNum'] * self.device.feed_conv_factor, None, weight, True)} {weight.symbol}",
                        "amount (volume)": f"{Unit.convert_feed(plan['grainNum'] * self.device.feed_conv_factor, None, volume, True)} {volume.symbol}",
                        "state": {
                            1: "Pending",
                            2: "Skipped",
                            3: "Completed",
                            4: "Skipped, Time Passed",
                        }.get(plan["state"], "Unknown"),
                        "repeat": plan["repeat"],
                        "planID": plan["planId"],
                    }
                    for plan in plans
                }
            case "next_feed_time":
                next_feed = self.device.get_next_feed
                next_feed_data = self.device.feeding_plan_data.get(
                    str(next_feed.get("id")), {}
                )
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
                    unit.symbol: Unit.convert_feed(
                        portion * self.device.feed_conv_factor, None, unit, True
                    )
                    for unit in (Unit.GRAMS, Unit.OUNCES)
                }
            case key if key in (
                "today_feeding_quantity_volume",
                "last_feed_quantity_volume",
                "next_feed_quantity_volume",
            ):
                portion = getattr(self.device, key.removesuffix("_volume"), 0)
                return {
                    unit.symbol: Unit.convert_feed(
                        portion * self.device.feed_conv_factor, None, unit, True
                    )
                    for unit in (Unit.CUPS, Unit.MILLILITERS)
                }
            case key if key in (
                "remaining_water",
                "today_drinking_amount",
                "yesterday_drinking_amount",
            ):
                key = "weight" if key == "remaining_water" else key
                return {
                    unit.symbol: VolumeConverter.convert(
                        getattr(self.device, key, 0),
                        UnitOfVolume.MILLILITERS,
                        unit.symbol,
                    )
                    for unit in VALID_UNIT_TYPES[API.WATER_UNIT]
                    if unit
                }
        return super().extra_state_attributes


DEVICE_SENSOR_MAP: dict[type[Device], list[PetLibroSensorEntityDescription]] = {
    Device: [  # common entities for all devices
        PetLibroSensorEntityDescription[Device](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            native_unit_of_measurement="dBm",
        ),
        PetLibroSensorEntityDescription[Device](
            key="wifi_ssid",
            translation_key="wifi_ssid",
        ),
    ],
    Feeder: [  # common entities for all feeders
        PetLibroSensorEntityDescription[Feeder](
            key="battery_state",
            translation_key="battery_state",
        ),
        PetLibroSensorEntityDescription[Feeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[Feeder](
            key="feeding_plan_state",
            translation_key="feeding_plan_state",
            should_report=lambda device: device.feeding_plan_state is not None,
        ),
    ],
    DryFoodFeeder: [  # common entities for all dry food feeders
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="last_feed_quantity_volume",
            translation_key="last_feed_quantity_volume",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="last_feed_quantity_weight",
            translation_key="last_feed_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="last_feed_time",
            translation_key="last_feed_time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="next_feed_quantity_volume",
            translation_key="next_feed_quantity_volume",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="next_feed_time",
            translation_key="next_feed_time",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="today_feeding_quantity_volume",
            translation_key="today_feeding_quantity_volume",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="today_feeding_quantity_weight",
            translation_key="today_feeding_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[DryFoodFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ],
    AirSmartFeeder: [
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[AirSmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
        ),
    ],
    GranarySmartFeeder: [
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="d",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[GranarySmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
        ),
    ],
    GranarySmartCameraFeeder: [
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="d",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="resolution",
            translation_key="resolution",
            should_report=lambda device: device.resolution is not None,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="night_vision",
            translation_key="night_vision",
            should_report=lambda device: device.night_vision is not None,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="enable_video_record",
            translation_key="enable_video_record",
            should_report=lambda device: device.enable_video_record is not None,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="video_record_switch",
            translation_key="video_record_switch",
            should_report=lambda device: device.video_record_switch is not None,
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="video_record_mode",
            translation_key="video_record_mode",
            should_report=lambda device: device.video_record_mode is not None,
        ),
    ],
    OneRFIDSmartFeeder: [
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="d",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_eating_times",
            translation_key="today_eating_times",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_eating_time",
            translation_key="today_eating_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="display_selection",
            translation_key="display_selection",
        ),
    ],
    PolarWetFoodFeeder: [
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="next_feeding_day",
            translation_key="next_feeding_day",
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="next_feeding_time",
            translation_key="next_feeding_time",
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="next_feeding_end_time",
            translation_key="next_feeding_end_time",
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="temperature",
            translation_key="temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement="°F",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[PolarWetFoodFeeder](
            key="plate_position",
            translation_key="plate_position",
            should_report=lambda device: device.plate_position is not None,
        ),
    ],
    SpaceSmartFeeder: [
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="next_feed_quantity_weight",
            translation_key="next_feed_quantity_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            petlibro_unit=API.FEED_UNIT,
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="pump_air_state",
            translation_key="pump_air_state",
        ),
        PetLibroSensorEntityDescription[SpaceSmartFeeder](
            key="vacuum_mode",
            translation_key="vacuum_mode",
        ),
    ],
    Fountain: [  # common entities for all fountains
        PetLibroSensorEntityDescription[Fountain](
            key="remaining_cleaning_days",
            translation_key="remaining_cleaning_days",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="d",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="remaining_filter_days",
            translation_key="remaining_filter_days",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="d",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[Fountain](
            key="remaining_water",
            translation_key="remaining_water",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[Fountain](
            key="weight_percent",
            translation_key="weight_percent",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_drinking_amount",
            translation_key="today_drinking_amount",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="yesterday_drinking_amount",
            translation_key="yesterday_drinking_amount",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_drinking_time",
            translation_key="today_drinking_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_avg_time",
            translation_key="today_avg_time",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="today_drinking_count",
            translation_key="today_drinking_count",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="yesterday_drinking_count",
            translation_key="yesterday_drinking_count",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="use_water_interval",
            translation_key="use_water_interval",
            native_unit_of_measurement="min",
        ),
        PetLibroSensorEntityDescription[DockstreamSmartFountain](
            key="use_water_duration",
            translation_key="use_water_duration",
            native_unit_of_measurement="min",
        ),
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="use_water_interval",
            translation_key="use_water_interval",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="min",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
            key="use_water_duration",
            translation_key="use_water_duration",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement="min",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        # Does not work with multi pet tracking, but may use this code later once I have the API info for the RFID tags.
        # PetLibroSensorEntityDescription[DockstreamSmartRFIDFountain](
        #     key="today_drinking_amount",
        #     translation_key="today_drinking_amount",
        #     device_class=SensorDeviceClass.VOLUME,
        #     state_class=SensorStateClass.TOTAL_INCREASING,
        #     petlibro_unit=API.WATER_UNIT,
        # ),
    ],
    Dockstream2SmartCordlessFountain: [
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_drinking_amount",
            translation_key="today_drinking_amount",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="yesterday_drinking_amount",
            translation_key="yesterday_drinking_amount",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="battery_state",
            translation_key="battery_state",
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="electric_quantity",
            translation_key="electric_quantity",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="battery_charge_state",
            translation_key="battery_charge_state",
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_drinking_time",
            translation_key="today_drinking_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_avg_time",
            translation_key="today_avg_time",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="today_drinking_count",
            translation_key="today_drinking_count",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartCordlessFountain](
            key="yesterday_drinking_count",
            translation_key="yesterday_drinking_count",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ],
    Dockstream2SmartFountain: [
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_drinking_amount",
            translation_key="today_drinking_amount",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="yesterday_drinking_amount",
            translation_key="yesterday_drinking_amount",
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            petlibro_unit=API.WATER_UNIT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_drinking_time",
            translation_key="today_drinking_time",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_avg_time",
            translation_key="today_avg_time",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="today_drinking_count",
            translation_key="today_drinking_count",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PetLibroSensorEntityDescription[Dockstream2SmartFountain](
            key="yesterday_drinking_count",
            translation_key="yesterday_drinking_count",
            state_class=SensorStateClass.TOTAL_INCREASING,
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
            _LOGGER.debug(
                "Adding sensor entity: %s for device %s",
                entity.entity_description.name,
                entity.device.name,
            )

    # Create Member sensor entity for front-end use.
    if member:
        entities.append(MemberEntity(member))
        _LOGGER.debug("Adding sensor entity for Petlibro member: %s", member.email)

    if entities:
        # Add sensor entities to Home Assistant
        async_add_entities(entities)
