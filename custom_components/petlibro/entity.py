"""PETLIBRO entities for common data and methods."""

from __future__ import annotations

from typing import Generic, TypeVar
from functools import cached_property
from datetime import datetime
import time

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .devices.device import Device, FRESHNESS_LIVE, FRESHNESS_CACHED, FRESHNESS_STALE, CONNECTION_ONLINE, DEFAULT_CACHE_MAX_AGE
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


class EnhancedPetLibroEntity(
    CoordinatorEntity[DataUpdateCoordinator[bool]], Generic[_DeviceT]
):
    """Enhanced PETLIBRO entity with improved reliability features."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self, 
        device: _DeviceT, 
        hub: PetLibroHub, 
        description: PetLibroEntityDescription[_DeviceT],
        staleness_threshold: int = DEFAULT_CACHE_MAX_AGE,  # Default to 1 hour
    ) -> None:
        """Initialize with enhanced features."""
        super().__init__(hub.coordinator)
        self.device = device
        self.hub = hub
        self.entity_description = description
        self._attr_unique_id = f"{self.device.serial}-{description.key}"
        self.staleness_threshold = staleness_threshold
        
        # If the device has a MAC address, include it in the unique ID
        mac_address = getattr(device, "mac", None)
        if mac_address:
            self._attr_unique_id = f"{device.serial}-{description.key}-{mac_address.replace(':', '')}"
    
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
    
    @property
    def available(self) -> bool:
        """Return if entity is available.
        
        An entity is considered available if the device has any data,
        live or cached.
        """
        return self.device.available
    
    def get_attribute_age(self, attribute: str) -> int:
        """Get the age of an attribute in seconds."""
        if hasattr(self.device, "get_attribute_age"):
            return self.device.get_attribute_age(attribute)
        elif hasattr(self.device, "_cached_attributes") and attribute in self.device._cached_attributes:
            return int(time.time() - self.device._cached_attributes[attribute])
        return 0
    
    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes with data freshness information."""
        attrs = {}
        
        # Add data freshness information
        if hasattr(self.device, "data_freshness"):
            attrs["data_freshness"] = self.device.data_freshness
        
        # Add connection state
        if hasattr(self.device, "connection_state"):
            attrs["connection_state"] = self.device.connection_state
            
            # Add human-readable connection status
            if self.device.connection_state == CONNECTION_ONLINE:
                attrs["connection_status"] = "Connected"
            elif self.device.connection_state == "degraded":
                attrs["connection_status"] = "Partially Connected"
            elif self.device.connection_state == "offline":
                attrs["connection_status"] = "Disconnected"
            else:
                attrs["connection_status"] = "Unknown"
        
        # Add last update time
        if hasattr(self.device, "last_updated"):
            last_updated = self.device.last_updated
            attrs["last_updated"] = last_updated
            
            # Add human-readable last updated time
            attrs["last_updated_time"] = datetime.fromtimestamp(last_updated).strftime("%Y-%m-%d %H:%M:%S")
            
            # Add age in minutes
            age_minutes = int((time.time() - last_updated) / 60)
            attrs["age_minutes"] = age_minutes
        
        # Check if this specific attribute is from cache
        key = self.entity_description.key
        if hasattr(self.device, "is_attribute_cached") and self.device.is_attribute_cached(key):
            attrs["from_cache"] = True
            
            # Add staleness indicator if the data is old
            age = self.get_attribute_age(key)
            attrs["attribute_age"] = age
            if age > self.staleness_threshold:
                attrs["stale"] = True
        
        return attrs

class PetLibroEntityDescription(EntityDescription, Generic[_DeviceT]):
    """PETLIBRO Entity description"""
