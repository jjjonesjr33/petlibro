"""Petlibro exceptions."""

from homeassistant.exceptions import HomeAssistantError


class PetLibroAPIError(HomeAssistantError):
    """Basic API error."""


class PetLibroCannotConnect(PetLibroAPIError):
    """Error to indicate we cannot connect."""


class PetLibroInvalidAuth(PetLibroAPIError):
    """Error to indicate there is invalid auth."""
