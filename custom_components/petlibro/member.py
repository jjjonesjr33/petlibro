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
    DOMAIN,
    CommonAPIKeys as API,
    Gender,
    UnitTypes,
)
from .devices.event import EVENT_UPDATE, Event

_LOGGER = getLogger(__name__)


class Member(Event):
    """Object representing the user's Petlibro account."""

    def __init__(self, data: dict, api: PetLibroAPI) -> None:
        """Initialise the Member object."""
        super().__init__()
        self._data: dict[str, str | Any] = {}
        self.force_refresh: bool = False
        self.api = api
        self.update_data(data)

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
        return f"PL-{self._data.get(API.ACCOUNT_ID, API.EMAIL)}-data"


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
    def gender(self) -> str:
        """Gender on account as a string."""
        try:
            return Gender(self._data.get(API.GENDER, 0)).name.lower()
        except ValueError:
            _LOGGER.error("Unknown gender value: %s", self._data.get("gender"))
            return str(Gender.NONE).lower()

    @property
    def weightUnitType(self) -> str:
        """Weight unit type on account as a string."""
        return self._get_unit_type(API.WEIGHT_UNIT, DEFAULT_WEIGHT).lower()

    @property
    def feedUnitType(self) -> str:
        """Feed unit type on account as a string."""
        return self._get_unit_type(API.FEED_UNIT, DEFAULT_FEED).lower()

    @property
    def waterUnitType(self) -> str:
        """Water unit type on account as a string."""
        return self._get_unit_type(API.WATER_UNIT, DEFAULT_WATER).lower()

    def _get_unit_type(self, key: str, default: UnitTypes) -> str:
        """Return a valid UnitTypes name for the given key."""
        raw_value = self._data.get(key, default)
        try:
            return UnitTypes(raw_value).name
        except ValueError:
            _LOGGER.error("Unknown unit type for %s: %s", key, raw_value)
            return default.name

    def to_dict(self) -> dict[str, Any]:
        """Return all key attributes as a dictionary."""
        return {
            "email": self.email,
            "nickname": self.nickname,
            "gender": self.gender.capitalize(),
            "weight_unit": self.weightUnitType.capitalize(),
            "feed_unit": self.feedUnitType.capitalize(),
            "water_unit": self.waterUnitType.capitalize(),
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
