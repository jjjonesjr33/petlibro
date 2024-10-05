"""Support for PETLIBRO sensors."""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from collections.abc import Callable
from datetime import datetime
from functools import cached_property
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


class PetLibroSensorEntity(PetLibroEntity[_DeviceT], SensorEntity):  # type: ignore [reportIncompatibleVariableOverride]
    """PETLIBRO sensor entity."""

    entity_description: PetLibroSensorEntityDescription[_DeviceT]  # type: ignore [reportIncompatibleVariableOverride]

    @cached_property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        if self.entity_description.should_report(self.device):
            if isinstance(val := getattr(self.device, self.entity_description.key), str):
                return val.lower()
            return cast(float | datetime | None, val)
        return None

    @cached_property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon

    @cached_property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement to use in the frontend, if any."""
        if (native_unit_of_measurement := self.entity_description.native_unit_of_measurement_fn(self.device)) is not None:
            return native_unit_of_measurement
        return super().native_unit_of_measurement

    @cached_property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        if (device_class := self.entity_description.device_class_fn(self.device)) is not None:
            return device_class
        return super().device_class


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
            unique_id_fn=lambda device: f"{device.id}-device_sn"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="mac_address",
            translation_key="mac_address",
            icon="mdi:network",
            unique_id_fn=lambda device: f"{device.id}-mac_address"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="wifi_ssid",
            translation_key="wifi_ssid",
            icon="mdi:wifi",
            unique_id_fn=lambda device: f"{device.id}-wifi_ssid"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="wifi_rssi",
            translation_key="wifi_rssi",
            icon="mdi:wifi",
            native_unit_of_measurement="dBm",
            unique_id_fn=lambda device: f"{device.id}-wifi_rssi"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="remaining_desiccant",
            translation_key="remaining_desiccant",
            icon="mdi:package",
            unique_id_fn=lambda device: f"{device.id}-remaining_desiccant"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="barn_door_state",
            translation_key="barn_door_state",
            icon="mdi:door",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-barn_door_state"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="power_mode",
            translation_key="power_mode",
            icon="mdi:power-plug",
            unique_id_fn=lambda device: f"{device.id}-power_mode"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_auto_upgrade",
            translation_key="enable_auto_upgrade",
            icon="mdi:refresh-auto",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-enable_auto_upgrade"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_offline_notice",
            translation_key="enable_offline_notice",
            icon="mdi:cloud-off-outline",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-enable_offline_notice"
        ),
    # Controls
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            icon="mdi:calendar-check",
            unique_id_fn=lambda device: f"{device.id}-enable_feeding_plan"
        ),
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            icon="mdi:lock",
            unique_id_fn=lambda device: f"{device.id}-child_lock_switch"
        ),
    # Switches for Light and Sound
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="enable_light",
            translation_key="enable_light",
            icon="mdi:lightbulb-on-outline",
            unique_id_fn=lambda device: f"{device.id}-enable_light"
        ),
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="light_switch",
            translation_key="light_switch",
            icon="mdi:lightbulb",
            unique_id_fn=lambda device: f"{device.id}-light_switch"
        ),
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="enable_sound",
            translation_key="enable_sound",
            icon="mdi:volume-high",
            unique_id_fn=lambda device: f"{device.id}-enable_sound"
        ),
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="sound_switch",
            translation_key="sound_switch",
            icon="mdi:volume-mute",
            unique_id_fn=lambda device: f"{device.id}-sound_switch"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="volume",
            translation_key="volume",
            icon="mdi:volume-high",
            native_unit_of_measurement="%",
            unique_id_fn=lambda device: f"{device.id}-volume"
        ),
    # Sensors for monitoring
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="surplus_grain",
            translation_key="surplus_grain",
            icon="mdi:grain",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-surplus_grain"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="grain_outlet_state",
            translation_key="grain_outlet_state",
            icon="mdi:grain",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-grain_outlet_state"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="battery_state",
            translation_key="battery_state",
            icon="mdi:battery",
            unique_id_fn=lambda device: f"{device.id}-battery_state"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="electric_quantity",
            translation_key="electric_quantity",
            icon="mdi:battery",
            native_unit_of_measurement="%",
            unique_id_fn=lambda device: f"{device.id}-electric_quantity"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-online"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="running_state",
            translation_key="running_state",
            icon="mdi:run",
            unique_id_fn=lambda device: f"{device.id}-running_state"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-whether_in_sleep_mode"
        ),
    # Binary Sensors for Notices
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-enable_low_battery_notice"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_power_change_notice",
            translation_key="enable_power_change_notice",
            icon="mdi:power-plug-alert",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-enable_power_change_notice"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_grain_outlet_blocked_notice",
            translation_key="enable_grain_outlet_blocked_notice",
            icon="mdi:grain-off",
            device_class_fn=lambda _: SensorDeviceClass.BINARY,
            unique_id_fn=lambda device: f"{device.id}-enable_grain_outlet_blocked_notice"
        ),
    # Feeding
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_feeding_quantity",
            translation_key="today_feeding_quantity",
            icon="mdi:scale",
            native_unit_of_measurement_fn=unit_of_measurement_feeder,
            device_class_fn=device_class_feeder,
            state_class=SensorStateClass.TOTAL_INCREASING,
            unique_id_fn=lambda device: f"{device.id}-today_feeding_quantity"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_feeding_times",
            translation_key="today_feeding_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            unique_id_fn=lambda device: f"{device.id}-today_feeding_times"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](
            key="today_eating_times",
            translation_key="today_eating_times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            unique_id_fn=lambda device: f"{device.id}-today_eating_times"
        ),
        PetLibroSensorEntityDescription[OneRFIDSmartFeeder](            
            key="today_eating_time",
            translation_key="today_eating_time",
            native_unit_of_measurement="s",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
            unique_id_fn=lambda device: f"{device.id}-today_eating_time"
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
