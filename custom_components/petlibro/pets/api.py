"""Petlibro API functions related to pets."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from aiohttp import ClientSession
import logging
from typing import Any
from collections.abc import Mapping
from ..exceptions import PetLibroAPIError
from .const import PetAPIKey as API


_LOGGER = logging.getLogger(__name__)


class PL_PetAPI:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, session: ClientSession):
        self.hass = hass
        self.entry = entry
        self.session = session

    async def get_list(self) -> dict:
        """Get a dictionary of pets on the account."""
        _LOGGER.debug("Requesting dictionary of pets")
        try:
            data = await self.session.post("/member/pet/list", json={})
        except Exception as exc:
            raise PetLibroAPIError("Failed to fetch dictionary of pets") from exc

        if not isinstance(data, Mapping):
            raise PetLibroAPIError(f"Invalid pets response format: {data}")

        _LOGGER.debug("Pets dictionary retrieved successfully")
        return data

    async def get_details(self, pet_id: int) -> Mapping[str, Any]:
        """Get details for a pet."""
        _LOGGER.debug("Requesting pet details for id: %s", pet_id)
        try:
            data = await self.session.post("/member/pet/detailV2", json={"id": pet_id})
        except Exception as exc:
            raise PetLibroAPIError("Failed to fetch pet details") from exc

        if not isinstance(data, Mapping):
            raise PetLibroAPIError(f"Invalid pet details response format: {data}")

        _LOGGER.debug("Pet details retrieved successfully")
        return data

    async def get_bound_devices(self, pet_id: int) -> list[Mapping]:
        """Get list of devices bound to a pet."""
        _LOGGER.debug("Requesting devices bound to pet id: %s", pet_id)
        try:
            data = await self.session.post(
                "/device/devicePetRelation/getBoundDevices", json={API.PET_ID: pet_id}
            )
        except Exception as exc:
            raise PetLibroAPIError("Failed to fetch pet's bound devices") from exc

        if data and not isinstance(data, list):
            raise PetLibroAPIError(
                f"Invalid pet's bound devices response format: {data}"
            )

        _LOGGER.debug("Bound devices retrieved successfully")
        return data or []

    async def save_or_update(self, settings: Mapping[str, Any]) -> bool:
        """Save or update pet's settings."""
        try:
            _LOGGER.debug("Attempting to update pet settings: %s", settings)
            await self.session.post("/member/pet/saveOrUpdate", json=settings)
        except PetLibroAPIError:
            _LOGGER.exception("Failed to update pet settings.")
            return False

        _LOGGER.debug("Successfully updated pet settings.")
        return True

    async def goal_setting(self, pet_id: int, goal_name: str, value: float) -> bool:
        """Update pet's goal."""
        try:
            _LOGGER.debug(
                "Attempting to update %s for pet id %s to %s", goal_name, pet_id, value
            )
            await self.session.post(
                "/member/healthCare/goalSetting",
                json={"goalList": [{API.PET_ID: pet_id, goal_name: value}]},
            )
        except PetLibroAPIError:
            _LOGGER.exception("Failed to update pet goal.")
            return False

        _LOGGER.debug("Successfully updated pet goal.")
        return True
