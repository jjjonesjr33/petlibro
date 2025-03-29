import asyncio

from logging import getLogger
from asyncio import gather
from collections.abc import Mapping
from typing import List, Any, Optional, Dict
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_REGION, CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from aiohttp import ClientResponseError, ClientConnectorError

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, UPDATE_INTERVAL_SECONDS
from .const import (
    CONF_MIN_UPDATE_INTERVAL,
    CONF_MAX_UPDATE_INTERVAL,
    CONF_ADAPTIVE_POLLING,
    DEFAULT_NOTIFICATION_CONFIG
)
from .api import PetLibroAPI
from .api import PetLibroAPIError
from .devices import Device, product_name_map
 
from .command_queue import CommandQueue
from .task_manager import BackgroundTaskManager
from .state_cache import PetLibroStateCache
from .adaptive_coordinator import AdaptivePollingCoordinator
from .notification_manager import NotificationManager

_LOGGER = getLogger(__name__)

class PetLibroHub:
    """A PetLibro hub wrapper class."""

    def __init__(self, hass: HomeAssistant, data: Mapping[str, Any]) -> None:
        """Initialize the PetLibro Hub."""
        self.hass = hass
        self._data = data
        self.devices: List[Device] = []  # Initialize devices as an instance variable
        self.config_entry_id = data.get("config_entry_id", data.get("entry_id", "default"))
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

        _LOGGER.debug(f"Initializing PetLibroHub with email: {email}, region: {region}")
        
        # Initialize state cache
        self.state_cache = PetLibroStateCache(hass, self.config_entry_id)
        
        # Initialize command queue
        self.command_queue = CommandQueue(hass, self)
        
        # Initialize task manager
        self.task_manager = BackgroundTaskManager(hass)
        
        # Initialize notification manager
        notification_config = data.get("options", {}).get("notifications", DEFAULT_NOTIFICATION_CONFIG)
        self.notification_manager = NotificationManager(hass, self.config_entry_id, notification_config)

        # Initialize the PetLibro API instance
        self.api = PetLibroAPI(
            async_get_clientsession(hass),
            hass.config.time_zone,
            region,
            email,
            password,
            data.get(CONF_API_TOKEN),
            config_entry=None,  # This will be set later if needed
            hass=hass,
            cache=self.state_cache
        )
        
        # Set back-reference for token saving
        self.api.session.api = self.api

        # Determine whether to use adaptive polling
        use_adaptive_polling = data.get(CONF_ADAPTIVE_POLLING, True)
        
        if use_adaptive_polling:
            # Get min/max update intervals from config or use defaults
            min_update_seconds = data.get(CONF_MIN_UPDATE_INTERVAL, 30)
            max_update_seconds = data.get(CONF_MAX_UPDATE_INTERVAL, 600)
            
            # Setup AdaptivePollingCoordinator
            self.coordinator = AdaptivePollingCoordinator(
                hass,
                _LOGGER,
                name="petlibro_devices",
                update_method=self.refresh_devices,
                min_update_interval=timedelta(seconds=min_update_seconds),
                max_update_interval=timedelta(seconds=max_update_seconds),
                task_manager=self.task_manager
            )
            _LOGGER.info(f"Using adaptive polling with interval range {min_update_seconds}s to {max_update_seconds}s")
        else:
            # Use standard DataUpdateCoordinator with fixed interval
            self.coordinator = DataUpdateCoordinator(
                hass, _LOGGER, name="petlibro_devices", 
                update_method=self.refresh_devices,
                update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            )
        
        # Start the state cache background save
        self.state_cache.start_background_save()
        
        # Start the task manager
        self.hass.async_create_task(self.task_manager.async_start())
        
        # Set up notification manager
        self.hass.async_create_task(self.notification_manager.async_setup())

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
                    device = product_name_map[device_name](device_data, self.api, self.state_cache, self.command_queue)
                    self.devices.append(device)  # Add to device list
                    _LOGGER.debug(f"Successfully loaded device: {device_name} (Serial: {device_sn})")
                else:
                    _LOGGER.error(f"Unsupported device found: {device_name} (Serial: {device_sn})")

                # Mark the device as loaded to prevent duplicate API calls
                self.loaded_device_sn.add(device_sn)
                self.last_refresh_times[device_sn] = datetime.utcnow()  # Set the last refresh time to now

            # Start command queue processing after devices are loaded
            await self.command_queue.async_start()
            _LOGGER.debug("Command queue processing started")
            
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
            device_tasks = []
            for device in self.devices:
                device_tasks.append((device, self.task_manager.schedule_task(self._refresh_device_if_needed(device, now))))

            # Gather results, allowing for early returns on failures or no-op tasks
            results = []
            for device, task in device_tasks:
                if task is None:
                    continue
                try:
                    results.append((device, await task))
                except Exception as e:
                    results.append((device, e))

            # Log the results of the device refresh attempts
            for device, result in results:
                if result is None:
                    _LOGGER.debug(f"Refresh skipped for {device.name} (Serial: {device.serial}).")
                elif isinstance(result, Exception):
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

    async def _refresh_device_if_needed(self, device: Device, now: datetime) -> Optional[bool]:
        """Refresh a device only if enough time has passed since the last refresh."""
        device_sn = device.serial
        last_refresh_time = self.last_refresh_times.get(device_sn)

        # Log and skip refresh if the device has been recently refreshed
        if last_refresh_time and (now - last_refresh_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping refresh for {device_sn}, last refreshed at {last_refresh_time}.")
            return None

        try:
            # Attempt to refresh the device
            _LOGGER.debug(f"Refreshing device {device_sn}.")
            # Use task manager to execute device refresh with proper priority
            await self.task_manager.run_task(device.refresh())
            self.last_refresh_times[device_sn] = now  # Update last refresh time
            _LOGGER.debug(f"Device refresh complete for serial: {device_sn}.")
            return True

        except Exception as ex:
            _LOGGER.error(f"Error refreshing {device_sn}: {ex}")
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
    
    def get_task_manager_stats(self) -> dict:
        """Get statistics about the task manager.
        
        Returns:
            Dictionary with task manager statistics
        """
        return self.task_manager.get_stats()
        
    async def async_add_command(
        self, device_id: str, command: str, params: Optional[dict] = None, 
        callback=None, priority: int = 0
    ) -> str:
        """Add a command to the queue.
        
        Args:
            device_id: The ID of the device the command is for
            command: The command name (corresponds to API method name)
            params: Optional parameters for the command
            callback: Optional callback function to call when command completes
            priority: Command priority (higher number = higher priority)
            
        Returns:
            The ID of the queued command
        """
        command_id = await self.command_queue.async_add_command(
            device_id=device_id,
            command=command,
            params=params,
            callback=callback,
            priority=priority
        )
        _LOGGER.debug(
            "Command queued via hub: %s, device: %s, priority: %d, id: %s",
            command,
            device_id,
            priority,
            command_id
        )
        return command_id
    
    def get_command_status(self, command_id: str) -> Optional[dict]:
        """Get the status of a command.
        
        Args:
            command_id: The ID of the command
            
        Returns:
            Command status information or None if not found
        """
        return self.command_queue.get_command_status(command_id)
        
    def get_queue_stats(self) -> dict:
        """Get statistics about the command queue.
        
        Returns:
            dict: Dictionary with queue statistics
        """
        return self.command_queue.get_queue_stats()
    
    def get_adaptive_polling_stats(self) -> Optional[dict]:
        """Get statistics about adaptive polling if it's enabled.
        
        Returns:
            dict or None: Dictionary with adaptive polling statistics, or None if not enabled
        """
        if isinstance(self.coordinator, AdaptivePollingCoordinator):
            return self.coordinator.get_statistics()
        return None
    
    def register_device_activity(self, device_id: str, action: str) -> None:
        """Register device activity to temporarily increase polling frequency.
        
        Args:
            device_id: Device identifier that had activity
            action: The action that triggered the activity
        """
        if isinstance(self.coordinator, AdaptivePollingCoordinator):
            self.coordinator.register_activity(device_id, action)

    async def async_unload(self) -> bool:
        """Unload the hub and its devices."""
        _LOGGER.debug("Unloading PetLibro Hub and clearing devices.")
        
        # Stop command queue processing
        await self.command_queue.async_stop()
        
        # Stop task manager
        await self.task_manager.async_stop()
        
        # Save any pending state
        await self.state_cache.async_save_cache()
        
        self.devices.clear()  # Clears the device list
        self.last_refresh_times.clear()  # Clears refresh times as well
        
        return True
        
    def get_notification_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get notification history.
        
        Args:
            limit: Maximum number of history entries to return
            
        Returns:
            List of notification history entries
        """
        return self.notification_manager.get_history(limit)