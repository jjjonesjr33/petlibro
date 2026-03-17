"""Constants and Enums for Petlibro."""

from enum import IntEnum, StrEnum
from typing import Any

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, UnitOfMass, UnitOfVolume

type _Unit = Unit
SENTINEL = object()

DOMAIN = "petlibro"
GITHUB = "https://github.com/jjjonesjr33/petlibro"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_API_TOKEN = "api_token"
CONF_REGION = "region"

# Supported platforms
PLATFORMS = ["sensor", "switch", "button", "binary_sensor", "number", "select", "text", "date", "image", "update"]  # Add any other platforms as needed

# Update interval for device data in seconds
UPDATE_INTERVAL_SECONDS = 60  # You can adjust this value based on your needs


class Gender(IntEnum):
    """Gender/sex options."""

    # API value, MDI Icon, Symbol, Emoji
    NONE = 0, "mdi:gender-male-female", "\u26a5", ""
    MALE = 1, "mdi:gender-male", "\u2642", "\u2642\ufe0f"
    FEMALE = 2, "mdi:gender-female", "\u2640", "\u2640\ufe0f"
    # API value for NONE is 0 for the member, but None/null for pets.

    def __new__(cls, value: int, icon: str, symbol: str, emoji: str):
        "Ensures IntEnum functionality while allowing symbols."
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj._icon = icon  # noqa: SLF001
        obj._symbol = symbol  # noqa: SLF001
        obj._emoji = emoji  # noqa: SLF001
        return obj

    @property
    def lower(self) -> str:
        """Returns unit name in lower case."""
        return self.name.lower()

    @property
    def icon(self) -> str:
        """MDI icon for gender (eg. mdi:gender-male)."""
        return self._icon

    @property
    def symbol(self) -> str:
        """Symbol for gender (eg. \u26a5, \u2642, \u2640)."""
        return self._symbol

    @property
    def emoji(self) -> str:
        """Emoji for gender (eg. \u2642\ufe0f, \u2640\ufe0f)."""
        return self._emoji


class APIKey(StrEnum):
    """Common API JSON keys."""

    # Common
    ID = "id"

    # Member
    NAME = "name"
    EMAIL = "email"
    NICKNAME = "nickname"
    GENDER = "gender"
    AVATAR = "avatar"
    FEED_UNIT = "feedUnitType"
    WATER_UNIT = "waterUnitType"
    WEIGHT_UNIT = "weightUnitType"

    # Device
    WEIGHT = "weight"
    DEVICE_SN = "deviceSn"
    PRODUCT_ID = "productIdentifier"
    RFID = "rfid"


class Unit(IntEnum):
    """Weight, feed, and water units with symbols and conversion.
    
    KILOGRAMS, POUNDS, and WATER values can be converted using HA's built-in unit
    converter, so their 'factor's and 'device_class's likely won't be used much.
    
    WATER int values must be different to avoid aliasing. Take care when using .value
    """

    CUPS = 1, round(1/12, 16), "cups", ""
    OUNCES = 2, 0.35, UnitOfMass.OUNCES, "weight"
    GRAMS = 3, 10, UnitOfMass.GRAMS, "weight"
    MILLILITERS = 4, 20, UnitOfVolume.MILLILITERS, "volume"

    KILOGRAMS = 5, 1, UnitOfMass.KILOGRAMS, "weight"
    POUNDS = 6, 2.20459, UnitOfMass.POUNDS, "weight"

    WATER_OUNCES = 2 +6, 0.033814, UnitOfVolume.FLUID_OUNCES, "volume"
    WATER_MILLILITERS = 4 +6, 1, UnitOfVolume.MILLILITERS, "volume"

    def __new__(cls, value: int, factor: float, symbol: str, device_class: str):
        "Ensures IntEnum functionality while allowing extra attributes."
        
        obj = int.__new__(cls, value if value <= 6 else value - 6)
        obj._value_ = value
        obj._factor = factor  # noqa: SLF001
        obj._symbol = symbol  # noqa: SLF001
        obj._device_class = device_class  # noqa: SLF001
        return obj

    @property
    def lower(self) -> str:
        """Returns unit name in lower case."""
        return self.name.lower()

    @property
    def factor(self) -> float:
        """Returns unit conversion factor."""
        return self._factor

    @property
    def symbol(self) -> str:
        """Returns unit symbol."""
        return self._symbol

    @property
    def device_class(self) -> str:
        """Returns unit device class."""
        return self._device_class

    @classmethod
    def round(self, value: float, unit: _Unit) -> float:
        return round(value, ROUNDING_RULES.get(unit, 0))

    @classmethod
    def convert_feed(
        self, value: float, from_unit: _Unit | None, to_unit: _Unit | None, rounded: bool = False
    ):
        """Convert PetLibro feed units. Use **None** for portion unit (1/12th of a cup)."""
        if value and from_unit != to_unit:
            if not {from_unit, to_unit}.issubset(VALID_UNIT_TYPES[APIKey.FEED_UNIT]):
                raise ValueError(f"Incompatible conversion: {from_unit} -> {to_unit}")

            from_factor = from_unit.factor if from_unit else 1
            to_factor = to_unit.factor if to_unit else 1

            api_value = value / from_factor
            new_value = api_value * to_factor
        else:
            new_value = value

        if not to_unit:
            return round(new_value)
        if rounded:
            return Unit.round(new_value, to_unit)
        return new_value
    

DEFAULT_WEIGHT = Unit.POUNDS
DEFAULT_FEED = Unit.CUPS
DEFAULT_WATER = Unit.WATER_OUNCES
DEFAULT_PORTIONS_IN_CUP = 12
DEFAULT_MAX_FEED_PORTIONS = 48
VALID_UNIT_TYPES: dict[str, set[Unit]] = {
    APIKey.WEIGHT_UNIT: {Unit.POUNDS, Unit.KILOGRAMS, None},
    APIKey.FEED_UNIT: {Unit.CUPS, Unit.OUNCES, Unit.GRAMS, Unit.MILLILITERS, None},
    APIKey.WATER_UNIT: {Unit.WATER_OUNCES, Unit.WATER_MILLILITERS, None},
}
ROUNDING_RULES = {
    Unit.CUPS: 3, Unit.OUNCES: 2, Unit.POUNDS: 2, Unit.WATER_OUNCES: 2, Unit.KILOGRAMS: 2
}
WATER_MAPPING = {
    Unit.MILLILITERS: Unit.WATER_MILLILITERS, Unit.OUNCES: Unit.WATER_OUNCES
}


class IntegrationSetting(StrEnum):
    """Integration settings and their default values."""
    
    MANUAL_FEED_PORTIONS = "manual_feed_portions", False
    ENABLE_SHARED_PETS = "enable_shared_pets", True

    def __new__(cls, value: str, default: bool):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._default = default
        return obj

    @property
    def default(self) -> Any:
        """Default value."""
        return self._default
