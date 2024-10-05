"""Support for PETLIBRO binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from functools import cached_property
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .devices import Device
from .devices.feeders.granary_feeder import GranaryFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription
from . import PetLibroHubConfigEntry


@dataclass(frozen=True)
class PetLibroBinarySensorEntityDescription(BinarySensorEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device binary sensor entities."""

    device_class_fn: Callable[[_DeviceT], BinarySensorDeviceClass | None] = lambda _: None
    should_report: Callable[[_DeviceT], bool] = lambda _: True
    device_class: Optional[BinarySensorDeviceClass] = None


class PetLibroBinarySensorEntity(PetLibroEntity[_DeviceT], BinarySensorEntity):  # type: ignore [reportIncompatibleVariableOverride]
    """PETLIBRO sensor entity."""

    entity_description: PetLibroBinarySensorEntityDescription[_DeviceT]  # type: ignore [reportIncompatibleVariableOverride]

    @cached_property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device class to use in the frontend, if any."""
        return self.entity_description.device_class

    @cached_property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        if not self.entity_description.should_report(self.device):
            return False

        state = getattr(self.device, self.entity_description.key)
        return bool(state)

DEVICE_BINARY_SENSOR_MAP: dict[type[Device], list[PetLibroBinarySensorEntityDescription]] = {
    GranaryFeeder: [],
    OneRFIDSmartFeeder: [
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="door_state",
            translation_key="door_state",
            icon="mdi:door",
            device_class=BinarySensorDeviceClass.DOOR,
            should_report=lambda device: device.door_state is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="food_dispenser_state",
            translation_key="food_dispenser_state",
            icon="mdi:bowl-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_dispenser_state is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="door_blocked",
            translation_key="door_blocked",
            icon="mdi:door",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.door_blocked is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="food_low",
            translation_key="food_low",
            icon="mdi:bowl-mix-outline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.food_low is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="online",
            translation_key="online",
            icon="mdi:wifi",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            should_report=lambda device: device.online is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="running_state",
            translation_key="running_state",
            icon="mdi:run",
            device_class=BinarySensorDeviceClass.RUNNING,
            should_report=lambda device: device.running_state is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="whether_in_sleep_mode",
            translation_key="whether_in_sleep_mode",
            icon="mdi:sleep",
            device_class=BinarySensorDeviceClass.POWER,
            should_report=lambda device: device.whether_in_sleep_mode is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_low_battery_notice",
            translation_key="enable_low_battery_notice",
            icon="mdi:battery-alert",
            device_class=BinarySensorDeviceClass.BATTERY,  # Changed to BATTERY to differentiate
            should_report=lambda device: device.enable_low_battery_notice is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_power_change_notice",
            translation_key="enable_power_change_notice",
            icon="mdi:power-plug-alert",
            device_class=BinarySensorDeviceClass.SAFETY,  # Kept as SAFETY
            should_report=lambda device: device.enable_power_change_notice is not None,
        ),
        PetLibroBinarySensorEntityDescription[OneRFIDSmartFeeder](
            key="enable_grain_outlet_blocked_notice",
            translation_key="enable_grain_outlet_blocked_notice",
            icon="mdi:grain-off",
            device_class=BinarySensorDeviceClass.PROBLEM,
            should_report=lambda device: device.enable_grain_outlet_blocked_notice is not None,
        )
    ]
}

async def async_setup_entry(
    _: HomeAssistant,
    entry: PetLibroHubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO binary sensors using config entry."""
    hub = entry.runtime_data
    entities = [
        PetLibroBinarySensorEntity(device, hub, description)
        for device in hub.devices
        for device_type, entity_descriptions in DEVICE_BINARY_SENSOR_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]
    async_add_entities(entities)
