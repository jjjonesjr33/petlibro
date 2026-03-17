"""Helper methods for components within the Petlibro integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
from ..const import IntegrationSetting


_LOGGER = logging.getLogger(__name__)

def set_missing_config_options(hub) -> None:
    """Set user's missing/unset Config Entry options to their default."""
    hass: HomeAssistant = hub.hass
    entry: ConfigEntry = hub.entry
    options = entry.options or {}

    set_defaults = {}
    for setting in IntegrationSetting:
        if setting not in options:
            set_defaults[setting] = setting.default

    if "devices" not in options:
        set_defaults["devices"] = {}

    if "pets" not in options:
        set_defaults["pets"] = {}

    if set_defaults:
        hass.config_entries.async_update_entry(
            entry, options={**options, **set_defaults}
        )
        _LOGGER.debug(f"Config entry options updated with: {set_defaults}")
