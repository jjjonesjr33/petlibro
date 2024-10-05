"""Support for PETLIBRO sensors."""
# Disabled features currently show Unknown, until updated they will be disabled.

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from homeassistant.components.sensor.const import SensorStateClass, SensorDeviceClass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .devices import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.granary_feeder import GranaryFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from . import PetLibroHubConfigEntry
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription

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
        mac_address = getattr(device, "mac", None)  # Fetch the MAC address from the device
        if mac_address:
            self._attr_unique_id = f"{device.serial}-{description.key}-{mac_address.replace(':', '')}"
        else:
            self._attr_unique_id = f"{device.serial}-{description.key}"

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        # Handle the power_mode specifically
        if self.entity_description.key == "power_mode":
            power_mode = getattr(self.device, self.entity_description.key, None)
            if power_mode == 1:
                return "AC Power"
            elif power_mode == 2:
                return "Battery Power"
            else:
                return "Unknown"  # Handle cases where power_mode is not 1 or 2
    
        # Handle grain_outlet_state mapping with True/False values
        elif self.entity_description.key == "grain_outlet_state":
            grain_outlet_state = getattr(self.device, self.entity_description.key, None)
            if grain_outlet_state is True:
                return "Cleared"
            elif grain_outlet_state is False:
                return "Blocked"
            else:
                return "Unknown"  # Handle cases where the attribute is missing or not recognized
    
        # Handle volume with a default value if missing
        elif self.entity_description.key == "volume":
            volume = getattr(self.device, self.entity_description.key, None)
            return volume if volume is not None else "Unknown"
    
        # Handle today_eating_time in minutes and seconds format
        elif self.entity_description.key == "today_eating_time":
            eating_time_seconds = getattr(self.device, self.entity_description.key, 0)
            if eating_time_seconds:
                minutes = eating_time_seconds // 60
                seconds = eating_time_seconds % 60
                return f"{minutes}m {seconds}s"  # Return formatted string in minutes and seconds
            return "0m 0s"  # Fallback if there are no eating seconds
    
        # Default behavior for other sensors, with fallback if key doesn't exist
        if self.entity_description.should_report(self.device):
            val = getattr(self.device, self.entity_description.key, None)
            if isinstance(val, str):
                return val.lower()
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
        return self.entity_description.native_unit_of_measurement_fn(self.device)

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        return self.entity_description.device_class_fn(self.device)


DEVICE_SENSOR_MAP: dict[type[Device], list[PetLibroSensorEntityDescription]] = {
    GranaryFeeder: [
        PetLibroSensorEntityDescription[GranaryFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            icon="mdi:package"
        ),
        PetLibroSensorEntityDescription[GranaryFeeder](
            key="today_feeding_quantity",
            translation_key="today_feeding_quantity",
            icon="mdi:scale",
            native_unit_of_measurement_fn=unit_of_measurement_feeder,
            device_class_fn=device_class_feeder,
            state_class=SensorStateClass.TOTAL_INCREASING
        ),
        PetLibroSensorEntityDescription[GranaryFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING
        )
    ],
    OneRFIDSmartFeeder: [
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="device_sn",
            translation_key="device_sn",
            icon="mdi:identifier",
            name="Device Serial Number"
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
            name="WiFi SSID"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            name="WiFi Signal Strength (RSSI)"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            icon="mdi:package",
            name="Remaining Desiccant Days"
        ),
#        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
#            key="power_mode",
#            translation_key="power_mode",
#            icon="mdi:power-plug",
#            name="Power Mode"
#        ),
#        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
#            key="volume",
#            translation_key="volume",
#            icon="mdi:volume-high",
#            native_unit_of_measurement="%",
#            should_report=lambda device: hasattr(device, 'volume') and device.volume is not None,
#            name="Volume"
#        ),
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
            name="Battery / AC %"
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
#        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
#            key="grain_outlet_state",
#            translation_key="grain_outlet_state",
#            icon="mdi:alert",
#            should_report=lambda device: hasattr(device, 'grain_outlet_state') and device.grain_outlet_state is not None,
#            name="Dispenser Status"
#        ),
#        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
#            key="door_error_state",
#            translation_key="door_error_state",
#            icon="mdi:alert",
#            name="Door State"
#        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="screenDisplaySwitch",
            translation_key="screen_display_switch",
            icon="mdi:lightbulb",
            name="Display Enabled"
        ),
        # Would like to change child_lock_switch to a dropdown switch
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            icon="mdi:lock",
            name="Child Lock"
        ),
        # Would like to change coverCloseSpeed to a dropdown switch
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="coverCloseSpeed",
            translation_key="cover_close_speed",
            icon="mdi:run-fast",
            name="Lid Speed"
        ),
    ]
}


async def async_setup_entry(
    _: HomeAssistant,
    entry: PetLibroHubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO sensors using config entry."""
    hub = entry.runtime_data
    entities = [
        PetLibroSensorEntity(device, hub, description)
        for device in hub.devices
        for device_type, entity_descriptions in DEVICE_SENSOR_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]
    async_add_entities(entities)
