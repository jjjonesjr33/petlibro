"""Constants and Enums for Petlibro."""

from enum import IntEnum, StrEnum

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, UnitOfMass, UnitOfVolume

DOMAIN = "petlibro"

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_API_TOKEN = "api_token"
CONF_REGION = "region"

# Supported platforms
PLATFORMS = ["sensor", "switch", "button", "binary_sensor", "number", "select", "text", "update"]  # Add any other platforms as needed

# Update interval for device data in seconds
UPDATE_INTERVAL_SECONDS = 60  # You can adjust this value based on your needs


class UnitTypes(IntEnum):
    """Weight, feed, and water units with symbols."""

    CUPS = 1, "cup"
    OUNCES = 2, UnitOfMass.OUNCES
    GRAMS = 3, UnitOfMass.GRAMS
    MILLILITERS = 4, UnitOfVolume.MILLILITERS
    KILOGRAMS = 5, UnitOfMass.KILOGRAMS
    POUNDS = 6, UnitOfMass.POUNDS

    def __new__(cls, value: int, symbol: str):
        "Ensures IntEnum functionality while allowing symbols."
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj._symbol = symbol  # noqa: SLF001
        return obj

    def __str__(self) -> str:
        """Returns the name as a string."""
        return self.name

    def __json__(self) -> int:
        """Returns the int value when sending to the API."""
        return int(self)

    @property
    def symbol(self) -> str:
        """Returns unit symbol."""
        return self._symbol


DEFAULT_WEIGHT = UnitTypes.POUNDS
DEFAULT_FEED = UnitTypes.CUPS
DEFAULT_WATER = UnitTypes.OUNCES


class Gender(IntEnum):
    """Gender/sex options."""

    # API value, MDI Icon, Symbol, Emoji
    NONE = 0, "mdi:gender-male-female", "\u26a5", ""
    MALE = 1, "mdi:gender-male", "\u2642", "\u2642\ufe0f"
    FEMALE = 2, "mdi:gender-female", "\u2640", "\u2640\ufe0f"

    def __new__(cls, value: int, icon: str, symbol: str, emoji: str):
        "Ensures IntEnum functionality while allowing symbols."
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj._icon = icon  # noqa: SLF001
        obj._symbol = symbol  # noqa: SLF001
        obj._emoji = emoji  # noqa: SLF001
        return obj

    def __str__(self) -> str:
        """Returns the name as a string."""
        return self.name

    def __json__(self) -> int:
        """Returns the int value when sending to API."""
        return int(self)

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


class CommonAPIKeys(StrEnum):
    """Common API JSON keys."""

    ACCOUNT_ID = "id"
    EMAIL = "email"
    NICKNAME = "nickname"
    GENDER = "gender"
    FEED_UNIT = "feedUnitType"
    WATER_UNIT = "waterUnitType"
    WEIGHT_UNIT = "weightUnitType"
