"""Support for PETLIBRO sensors."""
from __future__ import annotations
from dataclasses import dataclass
from logging import getLogger
from collections.abc import Callable
from datetime import datetime
from .const import DOMAIN, VALID_UNIT_TYPES, Unit, APIKey as API
from homeassistant.components.sensor.const import SensorStateClass, SensorDeviceClass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import Platform, UnitOfMass, UnitOfVolume, UnitOfTime, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import VolumeConverter
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from .hub import PetLibroHub  # Adjust the import path as necessary
from .member import MemberEntity

from .devices import Device
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
from .pets.entity import PL_PetSensorEntity


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
        
        mac_address = getattr(device, "mac", None)
        if mac_address:
            self._attr_unique_id = f"{device.serial}-{description.key}-{mac_address.replace(':', '')}"
        else:
            self._attr_unique_id = f"{device.serial}-{description.key}"
        
        if unit_type := self.entity_description.petlibro_unit:
            device_class = self.entity_description.device_class
            self.hub.unit_entities.unique_ids[unit_type][Platform.SENSOR][device_class].append(self._attr_unique_id)
        
        self._last_sensor_state = {}

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""        
        match self.key:
            case "today_eating_time":
                return getattr(self.device, self.key, 0)
            case "today_drinking_time":
                return getattr(self.device, self.key, 0)
            case "today_avg_time":
                return getattr(self.device, self.key, 0)
            case "yesterday_drinking_time":
                return getattr(self.device, self.key, 0)
            case "wifi_rssi":
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
                if self.entity_description.should_report(self.device):
                    val = getattr(self.device, self.key, None)
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
                return "°F"
            case key if key in (
                "today_eating_time", 
                "today_drinking_time", 
                "today_avg_time"
            ):
                return UnitOfTime.SECONDS
            case key if key in (
                "remaining_cleaning_days", 
                "remaining_filter_days", 
                "remaining_desiccant"
            ):
                return UnitOfTime.DAYS
            case "wifi_rssi":
                return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
            case key if key in (
                "use_water_interval", 
                "use_water_duration"
            ):
                return UnitOfTime.MINUTES
            case key if key in (
                "weight_percent", 
                "electric_quantity"
            ):
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
        )
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
        )
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
            should_report=lambda device: device.night_vision is not None
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="enable_video_record",
            translation_key="enable_video_record",
            icon="mdi:video",
            name="Video Recording Enabled",
            should_report=lambda device: device.enable_video_record is not None
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="video_record_switch",
            translation_key="video_record_switch",
            icon="mdi:video-outline",
            name="Video Recording Switch",
            should_report=lambda device: device.video_record_switch is not None
        ),
        PetLibroSensorEntityDescription[GranarySmartCameraFeeder](
            key="video_record_mode",
            translation_key="video_record_mode",
            icon="mdi:motion-sensor",
            name="Video Recording Mode",
            should_report=lambda device: device.video_record_mode is not None
        )
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
    LumaSmartLitterBox: [
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            name="Wi-Fi SSID"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="Wi-Fi Signal Strength"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            name="Battery / AC %"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            name="Battery Level"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="remaining_replacement_days",
            translation_key="remaining_replacement_days",
            icon="mdi:air-filter",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Filter Replacement Days"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="remaining_cleaning_days",
            translation_key="remaining_cleaning_days",
            icon="mdi:broom",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Remaining Cleaning Days"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="remaining_mat_days",
            translation_key="remaining_mat_days",
            icon="mdi:rectangle-outline",
            native_unit_of_measurement="d",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            name="Mat Replacement Days"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="filter_state",
            translation_key="filter_state",
            icon="mdi:air-filter",
            name="Filter State"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="clean_state",
            translation_key="clean_state",
            icon="mdi:broom",
            name="Cleanliness State"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="mat_state",
            translation_key="mat_state",
            icon="mdi:rectangle-outline",
            name="Mat State"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="door_state",
            translation_key="door_state",
            icon="mdi:door",
            name="Door State"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="vacuum_mode",
            translation_key="vacuum_mode",
            icon="mdi:robot-vacuum",
            name="Vacuum Mode"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="throw_mode",
            translation_key="throw_mode",
            icon="mdi:delete-variant",
            name="Throw Mode"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="deodorization_mode",
            translation_key="deodorization_mode",
            icon="mdi:air-purifier",
            name="Deodorization Mode"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="garbage_warehouse_state",
            translation_key="garbage_warehouse_state",
            icon="mdi:delete-variant",
            name="Waste Bin State"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="running_state",
            translation_key="running_state",
            icon="mdi:state-machine",
            name="Running State"
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="exception_message",
            translation_key="exception_message",
            icon="mdi:alert-circle-outline",
            name="Exception Message",
            should_report=lambda device: bool(device.exception_message),
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="weight",
            translation_key="weight",
            icon="mdi:weight",
            native_unit_of_measurement="g",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            name="Litter Weight",
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="weight_percent",
            translation_key="weight_percent",
            icon="mdi:gauge",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Litter Level",
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="clean_mode",
            translation_key="clean_mode",
            icon="mdi:cog",
            name="Clean Mode",
        ),
        PetLibroSensorEntityDescription[LumaSmartLitterBox](
            key="volume",
            translation_key="volume",
            icon="mdi:volume-high",
            native_unit_of_measurement="%",
            state_class=SensorStateClass.MEASUREMENT,
            name="Volume",
        ),
    ],
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO sensors using config entry."""
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    if not (member := hub.member):
        _LOGGER.warning("No member found in hub during sensor setup.")

    if not (devices := hub.devices):
        _LOGGER.warning("No devices found in hub during sensor setup.")

    if not (pets := hub.pets):
        _LOGGER.warning("No pets found in hub during sensor setup.")

    if not (devices or member or pets):
        return

    entities = []

    if devices:
        _LOGGER.debug("Hub data: %s", hub)
        _LOGGER.debug("Devices in hub: %s", devices)

        entities.extend(
            [
                PetLibroSensorEntity(device, hub, description)
                for device in devices.values()
                for device_type, entity_descriptions in DEVICE_SENSOR_MAP.items()
                if isinstance(device, device_type)
                for description in entity_descriptions
            ]
        )

    if not entities:
        _LOGGER.warning("No device sensors added, entities list is empty!")
    else:
        _LOGGER.debug("Adding %d PetLibro sensors", len(entities))
        for entity in entities:
            _LOGGER.debug(
                "Adding sensor entity: %s for device %s",
                entity.entity_description.name,
                entity.device.name,
            )

    if member:
        entities.append(MemberEntity(member))
        _LOGGER.debug("Adding sensor entity for Petlibro member: %s", member.email)

    if pets:
        for pet in pets.values():
            entities.extend(pet.entities(PL_PetSensorEntity, hub))

    if entities:
        async_add_entities(entities)