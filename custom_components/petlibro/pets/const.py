"""Constants and Enums for Pets."""

from enum import IntEnum, StrEnum

class PetAPIKey(StrEnum):
    """Common API JSON keys related to Pets."""

    ID = "id"
    MEMBER_ID = "memberId"
    NAME = "name"
    WEIGHT = "weight"
    AVATAR = "avatar"
    BIRTHDAY = "birthday"
    PET_TYPE = "type"
    SEX = "gender"
    BREED_NAME = "breedName"
    BREED_ID = "breedId"
    PET_ID = "petId"
    STERILIZATION = "sterilization"
    TODAY_EAT_AMOUNT = "todayEatNum"
    RFID = "rfid"

class PetType(IntEnum):
    """Pet types."""

    # API value, MDI Icon, Emoji
    CUSTOM = 0, "mdi:paw", ""
    DOG = 1, "mdi:dog", "\N{DOG FACE}"
    CAT = 2, "mdi:cat", "\N{CAT FACE}"

    def __new__(cls, value: int, icon: str, emoji: str):
        "Ensures IntEnum functionality while allowing icons."
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj._icon = icon  # noqa: SLF001
        obj._emoji = emoji  # noqa: SLF001
        return obj

    @property
    def lower(self) -> str:
        """Returns unit name in lower case."""
        return self.name.lower()

    @property
    def icon(self) -> str:
        """MDI icon (eg. mdi:dog, mdi:cat)"""
        return self._icon

    @property
    def emoji(self) -> str:
        """Emoji icon (eg. 🐶, 🐱)"""
        return self._emoji
    
DEFAULT_PET_AVATAR = "media/my_pet_default_avatar.png"
