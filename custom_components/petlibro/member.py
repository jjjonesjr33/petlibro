"""Member object representing the user's Petlibro account."""

from __future__ import annotations

from logging import getLogger
from typing import Any

from homeassistant.components.sensor import SensorEntity

from .api import PetLibroAPI
from .const import (
    DEFAULT_FEED,
    DEFAULT_WATER,
    DEFAULT_WEIGHT,
    WATER_MAPPING,
    DOMAIN,
    APIKey as API,
    Gender,
    Unit,
)
from .devices.event import EVENT_UPDATE, Event

_LOGGER = getLogger(__name__)


class Member(Event):
    """Object representing the user's Petlibro account."""

    def __init__(self, api: PetLibroAPI) -> None:
        """Initialise the Member object."""
        super().__init__()
        self._data: dict[str, str | Any] = {}
        self.force_refresh: bool = False
        self.api = api

    def update_data(self, data: dict[str, Any]) -> None:
        """Save the member info from a data dictionary."""
        if not isinstance(data, dict):
            _LOGGER.warning("update_data called with non-dict: %s", data)
            raise TypeError
        _LOGGER.debug("Updating member data with new information.")
        self._data.update(data)
        self.emit(EVENT_UPDATE)
        _LOGGER.debug("Member data updated successfully.")

    async def refresh(self) -> None:
        """Refresh the member info from the API."""
        new_data = await self.api.member_info()
        self.update_data(new_data)

    @property
    def entity_id(self) -> str:
        """Entity ID."""
        return f"PL-{self._data.get(API.ID, API.EMAIL)}-data"

    @property
    def id(self) -> int:
        """Account ID."""
        return self._data.get(API.ID)

    @property
    def email(self) -> str:
        """Account email."""
        return self._data.get(API.EMAIL, "")

    @property
    def nickname(self) -> str:
        """Nickname on account."""
        return self._data.get(API.NICKNAME, "")

    # Alias
    name = nickname

    @property
    def gender(self) -> Gender:
        """Gender on account as an Enum."""
        try:
            return Gender(self._data.get(API.GENDER, 0))
        except ValueError:
            _LOGGER.error("Unknown gender value: %s", self._data.get("gender"))
            return Gender.NONE

    @property
    def weightUnitType(self) -> Unit:
        """Weight unit type on account as an Enum."""
        return self._get_unit_type(API.WEIGHT_UNIT, DEFAULT_WEIGHT)

    @property
    def feedUnitType(self) -> Unit:
        """Feed unit type on account as an Enum."""
        return self._get_unit_type(API.FEED_UNIT, DEFAULT_FEED)

    @property
    def waterUnitType(self) -> Unit:
        """Water unit type on account as an Enum."""
        water_unit = self._get_unit_type(API.WATER_UNIT, DEFAULT_WATER)
        return WATER_MAPPING.get(water_unit, water_unit)

    def _get_unit_type(self, key: str, default: Unit) -> Unit:
        """Return a valid Unit Enum for the given key."""
        raw_value = self._data.get(key, default)
        try:
            return Unit(raw_value)
        except ValueError:
            _LOGGER.error("Unknown unit type for %s: %s", key, raw_value)
            return default

    def to_dict(self) -> dict[str, Any]:
        """Return all key attributes as a dictionary."""
        return {
            "email": self.email,
            "nickname": self.nickname,
            "gender": self.gender.name.capitalize(),
            "weight_unit": self.weightUnitType.name.capitalize(),
            "feed_unit": self.feedUnitType.name.capitalize(),
            "water_unit": self.waterUnitType.name.removeprefix('WATER_').capitalize(),
        }

class MemberEntity(SensorEntity):
    """Entity storing member data for front-end use."""
    def __init__(self, member: Member) -> None:
        """Initialise the member entity."""
        self.data: dict[str, Any] = {}
        self.member = member
        self._attr_unique_id = self.member.entity_id
        self._attr_native_value = self.member.email
        self._attr_name = f"{DOMAIN.capitalize()} ({self.member.email})"
        self._attr_icon = "mdi:account"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Update the entity's extra attributes."""
        return dict(self.data)

    async def async_update(self) -> None:
        """Update the data for the entity."""
        self.data = self.member.to_dict()

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the member entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.member.on(EVENT_UPDATE, self.async_write_ha_state))
