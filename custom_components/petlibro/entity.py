"""PETLIBRO entities for common data and methods."""

from __future__ import annotations

from typing import Generic, TypeVar
from functools import cached_property

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_registry import (
    RegistryEntryDisabler,
    RegistryEntryHider,
    async_get as async_get_entity_registry,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .devices import Device
from .devices.event import EVENT_UPDATE
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
        self.member = hub.member
        self.entity_description = description
        self.key = description.key
        self._attr_unique_id = f"{self.device.serial}-{description.key}"

        if not self.device.device_id:
            self.device.set_device_id()
        if not self.device.saved_to_options:
            self.device.save_to_options()

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return the device information for a PETLIBRO."""
        assert self.device.serial
        return DeviceInfo(
            identifiers=self.device.device_identifiers,
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            manufacturer="PETLIBRO",
            model=self.device.model,
            name=self.device.name,
            sw_version=self.device.software_version,
            hw_version=self.device.hardware_version,
            serial_number=self.device.serial,
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.on(EVENT_UPDATE, self.async_write_ha_state))

class PetLibroEntityDescription(EntityDescription, Generic[_DeviceT]):
    """PETLIBRO Entity description"""


def disable_unsupported_entity_entries(
    hass: HomeAssistant,
    platform: Platform,
    entities: list[PetLibroEntity],
) -> None:
    """Disable existing registry entries for unsupported fixed capabilities."""
    entity_registry = async_get_entity_registry(hass)

    for entity in entities:
        supported_fn = getattr(entity.entity_description, "supported_fn", None)
        if supported_fn is None or supported_fn(entity.device):
            continue

        entity_id = entity_registry.async_get_entity_id(
            platform,
            DOMAIN,
            entity.unique_id,
        )
        if entity_id is None:
            continue

        registry_entry = entity_registry.async_get(entity_id)
        if registry_entry is None:
            continue

        changes = {}
        if registry_entry.disabled_by is None:
            changes["disabled_by"] = RegistryEntryDisabler.INTEGRATION
        if registry_entry.hidden_by is None:
            changes["hidden_by"] = RegistryEntryHider.INTEGRATION
        if changes:
            entity_registry.async_update_entity(entity_id, **changes)
