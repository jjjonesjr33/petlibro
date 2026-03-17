"""Support for PETLIBRO date entities."""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
import logging
from .const import DOMAIN
from homeassistant.components.date import DateEntity, DateEntityDescription

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .hub import PetLibroHub

from .devices import Device
from .pets.entity import PL_PetDateEntity
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription


_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class PetLibroDateEntityDescription(DateEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device date entities."""

class PetLibroDateEntity(PetLibroEntity[_DeviceT], DateEntity):
    """PETLIBRO date entity."""

    entity_description: PetLibroDateEntityDescription[_DeviceT]

            
DEVICE_DATE_MAP: dict[type[Device], list[PetLibroDateEntityDescription]] = {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro dates using config entry."""
    
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # ↓ Uncomment if device entities are added ↓
    """
    # Ensure that the devices are loaded
    if not (devices := hub.devices):
        _LOGGER.warning("No devices found in hub during date setup.")
    """

    # Ensure that the pets are loaded
    if not (pets := hub.pets):
        _LOGGER.warning("No pets found in hub during date setup.")

    if not (pets): # or devices
        return

    entities = []

    # ↓ Uncomment if device entities are added ↓
    """
    if devices:
        # Devices should already be loaded in the hub
        _LOGGER.debug("Devices in hub: %s", devices)

        # Create date entities for each device based on the date map
        entities.extend(
            [
                PetLibroDateEntity(device, hub, description)
                for device in devices.values()  # Iterate through devices from the hub
                for device_type, entity_descriptions in DEVICE_DATE_MAP.items()
                if isinstance(device, device_type)
                for description in entity_descriptions
            ]
        )

    if not entities:
        _LOGGER.warning("No device dates added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro dates", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding date entity: %s for device %s", entity.entity_description.name, entity.device.name)
    """
    
    if pets:
        for pet in pets.values():
            entities.extend(pet.entities(PL_PetDateEntity, hub))

    if entities:
        # Add date entities to Home Assistant
        async_add_entities(entities)
