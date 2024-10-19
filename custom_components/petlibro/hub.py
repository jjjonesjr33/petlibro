import asyncio

from logging import getLogger
from asyncio import gather
from collections.abc import Mapping
from typing import List, Any, Optional
from datetime import datetime, timedelta
from .const import UPDATE_INTERVAL_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_REGION, CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from aiohttp import ClientResponseError, ClientConnectorError
from .api import PetLibroAPI  # Use a relative import if inside the same package
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD  # Import CONF_EMAIL and CONF_PASSWORD
from .api import PetLibroAPIError
from .devices import Device, product_name_map

_LOGGER = getLogger(__name__)

class PetLibroHub:
    """A PetLibro hub wrapper class."""

    def __init__(self, hass: HomeAssistant, data: Mapping[str, Any]) -> None:
        """Initialize the PetLibro Hub."""
        self.hass = hass
        self._data = data
        self.devices: List[Device] = []  # Initialize devices as an instance variable
        self.last_refresh_times = {}  # Track the last refresh time for each device
        self.loaded_device_sn = set()  # Track device serial numbers that have already been loaded
        self._last_online_status = {}  # Store online status per device

        # Fetch email, password, and region from entry.data
        email = data.get(CONF_EMAIL)
        password = data.get(CONF_PASSWORD)
        region = data.get(CONF_REGION)

        # Check if the required information is provided
        if not email:
            _LOGGER.error("Email is missing in the configuration entry.")
            raise ValueError("Email is required to initialize PetLibroAPI.")
        if not password:
            _LOGGER.error("Password is missing in the configuration entry.")
            raise ValueError("Password is required to initialize PetLibroAPI.")
        if not region:
            _LOGGER.error("Region is missing in the configuration entry.")
            raise ValueError("Region is required to initialize PetLibroAPI.")

        _LOGGER.debug(f"Initializing PetLibroAPI with email: {email}, region: {region}")

        # Initialize the PetLibro API instance
        self.api = PetLibroAPI(
            async_get_clientsession(hass),
            hass.config.time_zone,
            region,
            email,
            password,
            data.get(CONF_API_TOKEN)
        )

        # Setup DataUpdateCoordinator to periodically refresh device data
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="petlibro_devices",
            update_method=self.refresh_devices,  # Calls the refresh_devices method
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),  # Use defined interval
        )

    async def load_devices(self) -> None:
        """Load devices from the API and initialize them."""
        try:
            device_list = await self.api.list_devices()
            _LOGGER.debug(f"Fetched {len(device_list)} devices from the API.")

            if not device_list:
                _LOGGER.warning("No devices found in the API response.")
                return  # Early return if no devices found

            for device_data in device_list:
                device_sn = device_data.get("deviceSn", "unknown")
                device_name = device_data.get("productName", "unknown")
                _LOGGER.debug(f"Processing device: {device_name} (Serial: {device_sn})")

                # Check if the device is already loaded
                if device_sn in self.loaded_device_sn:
                    _LOGGER.debug(f"Device {device_sn} is already loaded, skipping further initialization.")
                    continue

                # Create a new device and add it without calling refresh immediately
                if device_name in product_name_map:
                    _LOGGER.debug(f"Loading new device: {device_name} (Serial: {device_sn})")
                    device = product_name_map[device_name](device_data, self.api)
                    self.devices.append(device)  # Add to device list
                    _LOGGER.debug(f"Successfully loaded device: {device_name} (Serial: {device_sn})")
                else:
                    _LOGGER.error(f"Unsupported device found: {device_name} (Serial: {device_sn})")

                # Mark the device as loaded to prevent duplicate API calls
                self.loaded_device_sn.add(device_sn)
                self.last_refresh_times[device_sn] = datetime.utcnow()  # Set the last refresh time to now

            _LOGGER.debug(f"Final devices loaded: {len(self.devices)} devices")
        except Exception as ex:
            _LOGGER.error(f"Error while loading devices: {ex}", exc_info=True)

    async def refresh_devices(self) -> bool:
        """Refresh all known devices from the PETLIBRO API."""
        if not self.devices:
            _LOGGER.warning("No devices to refresh.")
            return False

        try:
            now = datetime.utcnow()
            _LOGGER.debug("Starting the refresh process for all devices.")

            # Use a list to track refresh tasks and results for logging
            refresh_tasks = []
            for device in self.devices:
                refresh_tasks.append(self._refresh_device_if_needed(device, now))

            # Gather results, allowing for early returns on failures or no-op tasks
            results = await asyncio.gather(*refresh_tasks, return_exceptions=True)

            # Log the results of the device refresh attempts
            for device, result in zip(self.devices, results):
                if isinstance(result, Exception):
                    _LOGGER.error(f"Error refreshing {device.name} (Serial: {device.serial}): {result}")
                else:
                    _LOGGER.debug(f"Successfully refreshed {device.name} (Serial: {device.serial}).")

            _LOGGER.debug("Device refresh process completed.")
            return True

        except (PetLibroAPIError, ClientResponseError, ClientConnectorError) as ex:
            _LOGGER.error(f"API-related error during device refresh: {ex}", exc_info=True)
            raise UpdateFailed(f"Error updating PetLibro devices: {ex}")
        except Exception as ex:
            _LOGGER.error(f"Unexpected error during device refresh: {ex}", exc_info=True)
            raise UpdateFailed(f"Unexpected error: {ex}")

    async def _refresh_device_if_needed(self, device: Device, now: datetime) -> None:
        """Refresh a device only if enough time has passed since the last refresh."""
        device_sn = device.serial
        last_refresh_time = self.last_refresh_times.get(device_sn)

        # Log and skip refresh if the device has been recently refreshed
        if last_refresh_time and (now - last_refresh_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping refresh for {device_sn}, last refreshed at {last_refresh_time}.")
            return

        try:
            # Attempt to refresh the device
            _LOGGER.debug(f"Refreshing device {device_sn}.")
            await device.refresh()
            self.last_refresh_times[device_sn] = now  # Update last refresh time
            _LOGGER.debug(f"Device refresh complete for serial: {device_sn}.")

        except Exception as ex:
            _LOGGER.error(f"Error refreshing {device_sn}: {ex}", exc_info=True)
            raise

    async def get_device(self, serial: str) -> Optional[Device]:
        """Return the device with the specified serial number."""
        device = next((device for device in self.devices if device.serial == serial), None)
        if not device:
            _LOGGER.debug(f"Device with serial {serial} not found.")
        return device

    async def async_refresh(self) -> None:
        """Force a manual refresh of devices."""
        _LOGGER.debug("Manual refresh triggered for PetLibro devices.")
        await self.coordinator.async_request_refresh()

    async def async_unload(self) -> bool:
        """Unload the hub and its devices."""
        _LOGGER.debug("Unloading PetLibro Hub and clearing devices.")
        self.devices.clear()  # Clears the device list
        self.last_refresh_times.clear()  # Clears refresh times as well
        
        # No need to stop the coordinator explicitly
        return True