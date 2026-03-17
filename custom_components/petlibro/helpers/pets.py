"""."""

from collections.abc import Iterable
import logging
from typing import Literal

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..hub import PetLibroHub

_LOGGER = logging.getLogger(__name__)

PETS = "pets"


class PetsHelper:
    """."""

    def __init__(
        self, *, hass: HomeAssistant, config_entry: ConfigEntry, hub: PetLibroHub
    ):
        """Initialise the PetsHelper class."""
        self.hass = hass
        self.entry = config_entry
        self.handler = self.entry.entry_id
        self.hub = hub
        self.member = self.hub.member

        self.loaded_pet_ids = set()
        self.shared_pet_ids = set()
        _LOGGER.debug("Pets Helper initialised.")

    @property
    def cached_pets(self) -> dict:
        """Pets info saved to the Config Entry options table."""
        return self.entry.options.get(PETS, {})

    def _remove_device(self, device_id: str) -> None:
        """Remove a pet device entry from Home Assistant."""
        self.hub.device_register.async_update_device(
            device_id=device_id,
            remove_config_entry_id=self.handler,
        )
        _LOGGER.debug("Removed pet device: %s", device_id)

    def _sync_cache(self, new_pets_cache: dict) -> None:
        """Sync new pets info to the Config Entry options table."""
        if new_pets_cache != self.cached_pets:
            self.hub.update_options({PETS: new_pets_cache})

    async def remove_shared_pets(self) -> None:
        "Remove pet device entries that don't belong to this Petlibro account."
        _LOGGER.debug("Attempting to remove shared pets.")

        new_pets_cache = self.cached_pets.copy()
        for pet_id, pet in self.cached_pets.items():
            pet: dict
            device_id = pet.get("device_id")

            if not self.hub.device_register.async_get(device_id):
                new_pets_cache.pop(pet_id)
                _LOGGER.debug(
                    "Device ID %s for pet ID %s not found, removing from config entry options.",
                    device_id,
                    pet_id,
                )
                continue

            if not pet.get("owned"):
                self._remove_device(device_id)

        self._sync_cache(new_pets_cache)
        _LOGGER.debug("Successfully removed shared pets.")

    async def remove_pet_entries(
        self, pet_ids: int | Iterable[int] | Literal["all"], *, keep: bool = False
    ):
        """Remove pet device entries from Home Assistant.

        Args:
            pet_ids: Petlibro Pet IDs to act on, or "all".
            keep: Removes all pet devices *except* the given ones.
        """
        if isinstance(pet_ids, int):
            pet_ids = [pet_ids]

        new_pets_cache = self.cached_pets.copy()
        for pet_id, pet in self.cached_pets.items():
            pet: dict
            device_id = pet.get("device_id")

            if not self.hub.device_register.async_get(device_id):
                new_pets_cache.pop(pet_id)
                _LOGGER.debug(
                    "Device ID %s for pet ID %s not found, removing from config entry options.",
                    device_id,
                    pet_id,
                )
                continue

            matches = pet_ids == "all" or pet_id in pet_ids
            should_remove = matches if not keep else not matches

            if should_remove:
                self._remove_device(device_id)

        self._sync_cache(new_pets_cache)
