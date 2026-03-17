"""Support for PETLIBRO image entities."""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
import logging
from .const import DOMAIN
from homeassistant.components.image import ImageEntity, ImageEntityDescription

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .hub import PetLibroHub

from .devices import Device
from .pets.entity import PL_PetImageEntity
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription


_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True)
class PetLibroImageEntityDescription(ImageEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device image entities."""

class PetLibroImageEntity(PetLibroEntity[_DeviceT], ImageEntity):
    """PETLIBRO image entity."""

    entity_description: PetLibroImageEntityDescription[_DeviceT]

    def __init__(self, device, hub, description) -> None:
        """Initialise the image entity."""
        super().__init__(device, hub, description)
        ImageEntity.__init__(self, hub.hass)

            
DEVICE_IMAGE_MAP: dict[type[Device], list[PetLibroImageEntityDescription]] = {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Petlibro images using config entry."""

    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # ↓ Uncomment if device entities are added ↓
    """
    # Ensure that the devices are loaded
    if not (devices := hub.devices):
        _LOGGER.warning("No devices found in hub during image setup.")
    """

    # Ensure that the pets are loaded
    if not (pets := hub.pets):
        _LOGGER.warning("No pets found in hub during image setup.")

    if not (pets): # or devices
        return

    entities = []

    # ↓ Uncomment if device entities are added ↓
    """
    if devices:
        # Log the contents of the hub data for debugging
        _LOGGER.debug("Hub data: %s", hub)

        # Devices should already be loaded in the hub
        _LOGGER.debug("Devices in hub: %s", devices)

        # Create image entities for each device based on the image map
        entities.extend(
            [
                PetLibroImageEntity(device, hub, description)
                for device in devices.values()  # Iterate through devices from the hub
                for device_type, entity_descriptions in DEVICE_IMAGE_MAP.items()
                if isinstance(device, device_type)
                for description in entity_descriptions
            ]
        )

    if not entities:
        _LOGGER.warning("No device images added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro images", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding image entity: %s for device %s", entity.entity_description.name, entity.device.name)
    """
    
    if pets:
        for pet in pets.values():
            entities.extend(pet.entities(PL_PetImageEntity, hub))

    if entities:
        # Add image entities to Home Assistant
        async_add_entities(entities)
