"""PETLIBRO entities for common data and methods."""

from __future__ import annotations

from typing import Generic, TypeVar
from functools import cached_property
from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.components.sensor.const import SensorStateClass

from .devices import Device
from .devices.event import EVENT_UPDATE
from .const import DOMAIN
from .hub import PetLibroHub

_DeviceT = TypeVar("_DeviceT", bound=Device)


class PetLibroEntity(
    CoordinatorEntity[DataUpdateCoordinator[bool]], Generic[_DeviceT]
):
    """Generic PETLIBRO entity representing common data and methods."""

    _attr_has_entity_name = True

    def __init__(
        self, device: _DeviceT, hub: PetLibroHub, description: PetLibroEntityDescription[_DeviceT]
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(hub.coordinator)
        self.device = device
        self.hub = hub
        self.entity_description = description
        self._attr_unique_id = f"{self.device.serial}-{description.key}"

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return the device information for a PETLIBRO."""
        assert self.device.serial
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.serial)},
            manufacturer="PETLIBRO",
            model=self.device.model,
            name=self.device.name,
            sw_version=self.device.software_version,
            hw_version=self.device.hardware_version
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.on(EVENT_UPDATE, self.async_write_ha_state))

@dataclass(frozen=True)
class PetLibroEntityDescription(EntityDescription, Generic[_DeviceT]):
    """PETLIBRO Entity description"""

    key: str
    translation_key: str
    name: str
    icon: str | None = None
    state_class: SensorStateClass | None = None
