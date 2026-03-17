"""Pet object representing pet(s) on the user's Petlibro account."""

from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta
from logging import getLogger
import sys
from typing import Any

from ..api import PetLibroAPI
from .const import PetAPIKey as API, PetType
from ..const import (
    DOMAIN,
    Gender,
)
from ..devices.event import EVENT_UPDATE, Event
from ..member import Member

_LOGGER = getLogger(__name__)


class Pet(Event):
    """Object representing a pet."""

    def __init__(self, data: dict[str, str | Any], hub) -> None:
        """Initialise the Pet object."""
        super().__init__()
        if "PetLibroHub" not in sys.modules:
            from ..hub import PetLibroHub
        self.hub: PetLibroHub = hub
        self.member: Member = self.hub.member
        self.api: PetLibroAPI = self.hub.api
        self._data: dict[str, str | Any] = {}
        self.saved_to_options = False
        self.update_data(data)

    def entities(self, pet_entity, hub) -> list:
        """Create entites from the entity map."""
        if "PET_ENTITY_MAP" not in sys.modules:
            from .entity import PET_ENTITY_MAP
        entities = []
        entities.extend(
            [
                pet_entity(self, hub, description)
                for entity_type, entity_descriptions in PET_ENTITY_MAP.items()
                if entity_type == pet_entity
                for description in entity_descriptions
            ]
        )
        return entities

    def update_data(self, data: dict[str, Any]) -> None:
        """Save the pet info from a data dictionary."""
        if not isinstance(data, dict):
            _LOGGER.warning("update_data called with non-dict: %s", data)
            raise TypeError
        _LOGGER.debug("Updating pet data with new information.")
        self._data.update(data)
        self.emit(EVENT_UPDATE)
        _LOGGER.debug("Pet data updated successfully.")

    async def refresh(self) -> None:
        """Refresh the pet info from the API."""
        pet_details = await self.api.pets.get_details(self.id)
        bound_devices = await self.api.pets.get_bound_devices(self.id)
        self.update_data(
            {
                **pet_details,
                "boundDevices": bound_devices,
            }
        )

    def save_to_options(self) -> None:
        """Save data to the Config Entry about the pet."""
        if self.device_id:
            self.hub.update_options(
                {
                    "pets": self.hub.pets_helper.cached_pets
                    | {
                        str(self.id): {
                            "device_id": self.device_id,
                            "owned": self.owned,
                        },
                    }
                }
            )
            self.saved_to_options = True

    async def update_pet_settings(self, settings: dict[str, Any]) -> None:
        """Save pet settings on the account through the API."""
        update = self.required_for_update
        update.update(settings)
        await self.api.pets.save_or_update(update)
        await self.refresh()

    async def update_pet_goal(self, pet_id: int, goal_name: str, value: float) -> None:
        """Save pet goal on the account through the API."""
        await self.api.pets.goal_setting(pet_id, goal_name, value)
        await self.refresh()

    @property
    def required_for_update(self) -> dict[str, Any]:
        """Dict of required settings when updating a pet."""
        required = (
            API.AVATAR,
            API.BIRTHDAY,
            API.BREED_ID,
            API.SEX,
            API.NAME,
            API.STERILIZATION,
            API.BREED_NAME,
            API.PET_TYPE,
            API.WEIGHT,
            API.ID,
            "status",
            "activityLevel",
            "trainingGoal",
            "walkingGoal",
            "playingGoal",
            "appetiteLevel",
            "thirstLevel",
            "healthRisks",
            "mainPet",
            "behaviorAlertCount",
            "requiresRecognitionInfo",
        )
        return {key: self._data.get(key) for key in required}

    # --- Home Assistant Device

    @property
    def device_id(self) -> str:
        """Home Assistant Device ID of Pet."""
        return self._data.get("device_id") or ""

    @property
    def device_identifiers(self) -> set:
        """Home Assistant Device identifiers."""
        return {(DOMAIN, self.id)}

    def set_device_id(self) -> None:
        """Update Pet object data with it's Home Assistant device ID."""
        device = self.hub.device_register.async_get_device(
            identifiers=self.device_identifiers
        )
        if device and getattr(device, "id", False):
            self.update_data({"device_id": device.id})

    # --- Account

    @property
    def id(self) -> int:
        """ID of pet."""
        return self._data.get(API.ID)

    @property
    def memberId(self) -> int:
        """ID of pet's owner."""
        return self._data.get(API.MEMBER_ID)

    @property
    def owned(self) -> bool:
        """Whether this account owns the pet."""
        return self.memberId == self.member.id

    # --- Settings

    @property
    def name(self) -> str:
        """Name of pet."""
        return self._data.get(API.NAME) or ""

    @property
    def gender(self) -> Gender:
        """Sex of pet as an enum."""
        try:
            gen = Gender(self._data.get(API.SEX) or 0)
            return gen
        except ValueError:
            _LOGGER.error("Unknown gender value: %s", self._data.get(API.SEX))
            return Gender.NONE

    nickname = name
    sex = gender

    @property
    def breedName(self) -> str:
        """Breed of pet."""
        return str(self._data.get(API.BREED_NAME, ""))

    @property
    def breedId(self) -> int:
        """Breed ID of pet."""
        return int(self._data.get(API.BREED_ID)) or 0

    @property
    def type(self) -> PetType:
        """Pet type as an enum."""
        try:
            pet_type = PetType(self._data.get(API.PET_TYPE) or 0)
            return pet_type

            # return self.breedName.lower() or ""
        except ValueError:
            _LOGGER.error("Unknown pet type value: %s", self._data.get(API.PET_TYPE))
            return PetType.CUSTOM

    @property
    def avatar(self) -> str | None:
        """Avatar URL of pet."""
        return self._data.get(API.AVATAR) or None

    # --- Health

    @property
    def weight(self) -> float:
        """Weight of pet."""
        return self._data.get(API.WEIGHT) or 0

    @property
    def sterilization(self) -> bool:
        """Return true if pet is sterilized."""
        # 1 = Yes, 2 = No, None = Not selected
        return bool(self._data.get(API.STERILIZATION) == 1)

    @property
    def birthday(self) -> date | None:
        """Birthday of pet as a date object."""
        birthday = self._data.get(API.BIRTHDAY) or ""
        if birthday:
            return date.fromisoformat(birthday)
        return None

    def to_api_birthday(self, birthday: date) -> str:
        """Convert date object to api value (ISO)."""
        return birthday.isoformat()

    @property
    def age(self) -> relativedelta | None:
        """Age of pet."""
        if self.birthday:
            return relativedelta(date.today(), self.birthday)
        return None

    # --- Devices

    @property
    def boundDeviceNums(self) -> int:
        """Number of devices bound to pet."""
        return self._data.get("boundDeviceNums") or 0

    @property
    def boundDevices(self) -> list[dict]:
        """List of device details bound to pet."""
        return self._data.get("boundDevices") or list()

    @property
    def collarBindDeviceNum(self) -> int:
        """Number of devices bound to pet's collar."""
        return self._data.get("collarBindDeviceNum") or 0

    @property
    def rfid(self) -> str | None:
        """RFID of pet's collar if assigned."""
        return self._data.get(API.RFID)

    # --- Goals

    @property
    def feedingGoal(self) -> float:
        """Feeding goal of pet in portions."""
        return self._data.get("feedingGoal") or 0

    @property
    def drinkingGoal(self) -> float:
        """Drinking goal of pet in milliliters."""
        return self._data.get("drinkingGoal") or 0

    @property
    def weightGoal(self) -> float:
        """Weight goal of pet in Kilograms."""
        return self._data.get("weightGoal") or 0

    @property
    def activityGoal(self) -> float:
        """Activity goal of pet in minutes per day."""
        return self._data.get("activityGoal") or 0

    @property
    def playingGoal(self) -> float:
        """Playing goal of pet in minutes per day."""
        return self._data.get("playingGoal") or 0

    @property
    def trainingGoal(self) -> float:
        """Training goal of pet in minutes per day."""
        return self._data.get("trainingGoal") or 0

    @property
    def walkingGoal(self) -> float:
        """Walking goal of pet in minutes per day."""
        return self._data.get("walkingGoal") or 0

    # --- Activity

    @property
    def todayFeedTimes(self) -> int:
        """Number of times the pet ate today."""
        return self._data.get("todayFeedTimes") or 0

    @property
    def todayEatNum(self) -> float:
        """Amount pet ate today in portions."""
        return self._data.get(API.TODAY_EAT_AMOUNT) or 0
