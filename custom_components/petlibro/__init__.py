import logging

from datetime import timedelta  # For managing the update interval

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed  # For coordinator and update handling
from .devices import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.air_smart_feeder import AirSmartFeeder
from .devices.feeders.granary_smart_feeder import GranarySmartFeeder
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.feeders.polar_wet_food_feeder import PolarWetFoodFeeder
from .devices.feeders.space_smart_feeder import SpaceSmartFeeder
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain

from .const import (
    DOMAIN, CONF_EMAIL, CONF_PASSWORD, PLATFORMS, UPDATE_INTERVAL_SECONDS,
    CONF_MIN_UPDATE_INTERVAL, CONF_MAX_UPDATE_INTERVAL, CONF_ADAPTIVE_POLLING,
)
from .hub import PetLibroHub

_LOGGER = logging.getLogger(__name__)

# Configuration schema for YAML configuration
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Optional(CONF_MIN_UPDATE_INTERVAL, default=30): cv.positive_int,
            vol.Optional(CONF_MAX_UPDATE_INTERVAL, default=600): cv.positive_int,
            vol.Optional(CONF_ADAPTIVE_POLLING, default=True): cv.boolean,
        })
    }, extra=vol.ALLOW_EXTRA
)

# Define the platforms for each device type
PLATFORMS_BY_TYPE = {
    Feeder: (
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    AirSmartFeeder: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    GranarySmartFeeder: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    GranarySmartCameraFeeder: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    OneRFIDSmartFeeder: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
        Platform.NUMBER,
        Platform.SELECT,
        Platform.TEXT,
    ),
    PolarWetFoodFeeder: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    SpaceSmartFeeder: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    DockstreamSmartFountain: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
    DockstreamSmartRFIDFountain: (
        Platform.SENSOR,
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.BUTTON,
    ),
}


def get_platforms_for_devices(devices: list[Device]) -> set[Platform]:
    """Get platforms for devices."""
    return {
        platform
        for device in devices
        for device_type, platforms in PLATFORMS_BY_TYPE.items()
        if isinstance(device, device_type)
        for platform in platforms
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)

    # Ensure email and password exist
    if not email or not password:
        _LOGGER.error("Email or password is missing in the configuration entry. Cannot proceed.")
        return False

    # Initialize PetLibroHub
    try:
        hub = PetLibroHub(hass, entry.data)

        # Store the hub in hass.data
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

        # Load devices only once here
        await hub.load_devices()

        # Start the coordinator for periodic updates
        await hub.coordinator.async_config_entry_first_refresh()

        # Forward entry setups for each platform
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Register service to send test notification
        async def handle_test_notification(call):
            """Handle the service call to send a test notification."""
            hub = hass.data[DOMAIN][entry.entry_id]
            if hasattr(hub, "notification_manager"):
                await hub.notification_manager._send_notification(
                    message="This is a test notification from the PetLibro integration.",
                    title="PetLibro Test Notification",
                    notification_id="petlibro_test_notification",
                    importance="normal"
                )
            else:
                _LOGGER.error("Notification manager not available")

        # Register the service
        hass.services.async_register(
            DOMAIN,
            "send_test_notification",
            handle_test_notification
        )

        _LOGGER.info(f"Successfully set up PetLibro integration for {email}")
        return True

    except Exception as err:
        _LOGGER.error(f"Failed to set up PetLibro integration: {err}", exc_info=True)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Get the hub from Home Assistant's domain data
    hub = hass.data[DOMAIN].pop(entry.entry_id, None)

    if hub is None:
        _LOGGER.warning(f"PetLibro hub for entry {entry.entry_id} not found.")
        return False

    # Unload platforms associated with the entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.info(f"Successfully unloaded PetLibro entry for {entry.data.get(CONF_EMAIL)}")
        await hub.async_unload()  # If you have any cleanup to do in the hub
    else:
        _LOGGER.error(f"Failed to unload PetLibro entry for {entry.data.get(CONF_EMAIL)}")

    return unload_ok


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry) -> bool:
    """Remove a config entry from a device."""
    hub = hass.data[DOMAIN].get(entry.entry_id)
    
    if not hub:
        _LOGGER.warning("No hub found for this entry during device removal.")
        return False

    # Match the serial number with devices in the hub
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        for device in hub.devices
        if device.serial == identifier[1]
    )