"""Base device class for PetLibro devices with enhanced reliability."""
import asyncio
import time
from logging import getLogger
from typing import Any, Dict, List, Optional, Union, cast
from homeassistant.core import HomeAssistant

from ..api import PetLibroAPI
from ..command_queue import CommandQueue
from ..state_cache import PetLibroStateCache
from ..task_manager import BackgroundTaskManager
from .event import Event, EVENT_UPDATE

_LOGGER = getLogger(__name__)

# Constants for data freshness
FRESHNESS_LIVE = "live"
FRESHNESS_CACHED = "cached"
FRESHNESS_STALE = "stale"
FRESHNESS_PARTIAL_LIVE = "partial_live"

# Constants for connection state
CONNECTION_ONLINE = "online"
CONNECTION_DEGRADED = "degraded"
CONNECTION_OFFLINE = "offline"
CONNECTION_UNKNOWN = "unknown"

# Maximum age for cached data to be considered fresh (in seconds)
DEFAULT_CACHE_MAX_AGE = 3600  # 1 hour


class EnhancedDevice(Event):
    """Enhanced device base class with reliability improvements."""
    
    def __init__(
        self, 
        data: Dict[str, Any], 
        api: PetLibroAPI, 
        cache: Optional[PetLibroStateCache] = None,
        command_queue: Optional[CommandQueue] = None,
        task_manager: Optional[BackgroundTaskManager] = None,
        hass: Optional[HomeAssistant] = None
    ):
        """Initialize with enhanced components.
        
        Args:
            data: Initial device data
            api: PetLibro API client
            cache: Optional state cache reference
            command_queue: Optional command queue reference
            task_manager: Optional task manager reference
            command_queue: Optional command queue reference
        """
        super().__init__()
        self._data: Dict[str, Any] = {}
        self.api = api
        self._cache = cache  # State cache reference
        self.hass = hass or api.hass  # Use API's hass reference if not provided
        self._task_manager = task_manager  # Task manager reference
        self._command_queue = command_queue  # Command queue reference
        self._cached_attributes: Dict[str, float] = {}  # Track attributes from cache, with timestamps
        self._connection_state = CONNECTION_UNKNOWN  # Track connection state
        self._last_update_time = time.time()
        self._updating = False  # Lock to prevent concurrent updates
        
        # Initialize with data
        self.update_data(data)

    def update_data(self, data: Dict[str, Any]) -> None:
        """Save device info with cache update and data source tracking.
        
        This method updates the device data and tracks which attributes are 
        updated. It also updates the cache if provided and marks attributes
        as live (not from cache).
        
        Args:
            data: New device data
        """
        try:
            # Track which attributes have been updated
            updated_attrs = set()
            critical_states = {}
            
            _LOGGER.debug("Updating data with new information")
            for key, value in data.items():
                # Check for critical state changes
                if key in self._data:
                    old_value = self._data[key]
                    if old_value == value:
                        continue  # Skip unchanged values
                
    
                    # Check for critical state mapping
                    if key == "batteryState" and isinstance(value, (int, float)):
                        critical_states["battery"] = value
                    elif key == "waterLevel" and isinstance(value, (int, float)):
                        critical_states["water_level"] = value
                    elif key == "foodPercentage" and isinstance(value, (int, float)):
                        critical_states["food_level"] = value
                else:
                    # New value being added
                    if key == "batteryState" and isinstance(value, (int, float)):
                        critical_states["battery"] = value
                    elif key == "waterLevel" and isinstance(value, (int, float)):
                        critical_states["water_level"] = value
                    elif key == "foodPercentage" and isinstance(value, (int, float)):
                        critical_states["food_level"] = value
                
                # Update the data
                self._data[key] = value
                updated_attrs.add(key)
                
                # Mark as live data (not from cache)
                if key in self._cached_attributes:
                    del self._cached_attributes[key]
            
            # Update the cache if provided
            if self._cache and updated_attrs:
                cache_data = {k: self._data[k] for k in updated_attrs if k in self._data}
                self._cache.update_device_state(self.serial, cache_data)
            
            # Fire device state event for critical changes
            if critical_states and hasattr(self, 'hass') and self.hass:
                event_data = {
                    "device_id": self.serial,
                    "device_name": self.name
                }
                
                # Add critical states to event data
                for state_type, value in critical_states.items():
                    event_data[state_type] = value
                    
                # Fire event
                self.hass.bus.async_fire("petlibro_device_state", event_data)
            
            if updated_attrs:
                self._last_update_time = time.time()
                self.emit(EVENT_UPDATE)
                _LOGGER.debug(f"Updated {len(updated_attrs)} attributes: {', '.join(updated_attrs)}")

            else:
                _LOGGER.debug("No attributes changed, skipping update")
                
        except Exception as e:
            _LOGGER.error(f"Error updating data: {e}")

    async def refresh(self):
        """Refresh device data with parallel API calls and graceful degradation.
        
        This method performs parallel API calls to get device data, handles exceptions
        for each call separately, and falls back to cached data when needed.
        """
        if self._updating:
            _LOGGER.debug(f"Refresh already in progress for {self.serial}")
            return
            
        self._updating = True
        
        try:
            if self._task_manager:
                # Use task manager for parallel API calls with proper scheduling
                _LOGGER.debug(f"Using task manager for parallel API calls for {self.serial}")
                
                # Schedule API calls as separate tasks
                base_info_task = self._task_manager.schedule_task(self.api.device_base_info(self.serial))
                real_info_task = self._task_manager.schedule_task(self.api.device_real_info(self.serial))
                attribute_settings_task = self._task_manager.schedule_task(self.api.device_attribute_settings(self.serial))
                
                # Gather results with proper error handling
                results = []
                for i, task in enumerate([base_info_task, real_info_task, attribute_settings_task]):
                    if task:  # Task might be None if task_manager is shutting down
                        try:
                            results.append(await task)
                        except Exception as e:
                            results.append(e)
                    else:
                        results.append(Exception(f"Failed to schedule task {i} for {self.serial}"))
            else:
                # Legacy approach using asyncio.gather directly
                tasks = [self.api.device_base_info(self.serial), self.api.device_real_info(self.serial), self.api.device_attribute_settings(self.serial)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            data = {}
            success_count = 0
            failure_count = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failure_count += 1
                    _LOGGER.warning(f"API call {i} failed for {self.serial}: {result}")
                    
                    # Try to get cached data for this endpoint
                    if self._cache:
                        if i == 0:  # baseInfo
                            cached_base = self._get_cached_base_info()
                            if cached_base:
                                data.update(cached_base)
                        elif i == 1:  # realInfo
                            cached_real = self._get_cached_real_info()
                            if cached_real:
                                data.update(cached_real)
                        elif i == 2:  # attributeSettings
                            cached_attr = self._get_cached_attribute_settings()
                            if cached_attr:
                                data.update(cached_attr)
                else:
                    success_count += 1
                    data.update(result)

            # Update connection state based on success/failure ratio
            if success_count == len(results):
                self._connection_state = CONNECTION_ONLINE
            elif success_count > 0:
                self._connection_state = CONNECTION_DEGRADED
            else:
                self._connection_state = CONNECTION_OFFLINE
            
            # Update device data with whatever we have
            if data:
                self.update_data(data)
            else:
                _LOGGER.warning(f"No data available for {self.serial}, device may appear unavailable")
                
        except Exception as e:
            self._connection_state = CONNECTION_OFFLINE
            _LOGGER.error(f"Failed to refresh device {self.serial}: {e}")
            
        finally:
            self._updating = False

    def _get_cached_base_info(self) -> Dict[str, Any]:
        """Get cached base info for the device.
        
        Returns:
            Dictionary with cached base info or empty dict if not available
        """
        if not self._cache:
            return {}
            
        cached_state = self._cache.get_device_state(self.serial)
        if not cached_state:
            return {}
            
        # Extract base info keys from cached state (excluding ones with prefixes)
        base_keys = [
            k for k in cached_state.keys() 
            if not k.startswith("realInfo") and not k.startswith("attributeSetting")
        ]
        
        if not base_keys:
            return {}
            
        result = {k: cached_state[k] for k in base_keys}
        
        # Mark these attributes as coming from cache
        for k in base_keys:
            self._cached_attributes[k] = time.time()
            
        return result

    def _get_cached_real_info(self) -> Dict[str, Any]:
        """Get cached real info for the device.
        
        Returns:
            Dictionary with cached real info or empty dict if not available
        """
        if not self._cache:
            return {}
            
        cached_state = self._cache.get_device_state(self.serial)
        if not cached_state:
            return {}
            
        # Extract real info keys (typically starting with realInfo)
        real_keys = [k for k in cached_state.keys() if k.startswith("realInfo")]
        if not real_keys:
            return {}
            
        result = {k: cached_state[k] for k in real_keys}
        
        # Mark these attributes as coming from cache
        for k in real_keys:
            self._cached_attributes[k] = time.time()
            
        return result
        
    def _get_cached_attribute_settings(self) -> Dict[str, Any]:
        """Get cached attribute settings for the device.
        
        Returns:
            Dictionary with cached attribute settings or empty dict if not available
        """
        if not self._cache:
            return {}
            
        cached_state = self._cache.get_device_state(self.serial)
        if not cached_state:
            return {}
            
        # Extract attribute settings keys (typically starting with attributeSetting)
        attr_keys = [k for k in cached_state.keys() if k.startswith("attributeSetting")]
        if not attr_keys:
            return {}
            
        result = {k: cached_state[k] for k in attr_keys}
        
        # Mark these attributes as coming from cache
        for k in attr_keys:
            self._cached_attributes[k] = time.time()
            
        return result

    async def execute_command(self, command: str, **params) -> Any:
        """Execute a device command using the command queue.
        
        This method either adds the command to the queue or executes it directly
        if no queue is available.
        
        If task_manager is available, it will be used to handle resource-intensive
        operations as background tasks.
        
        Args:
            command: The command name
            **params: Command parameters
            
        Returns:
            Command ID if queued, or direct result if executed immediately
            
        Raises:
            ValueError: If the command is not supported by the device
        """
        return await self._execute_command_internal(command, False, **params)

    async def execute_critical_command(self, command: str, **params) -> Any:
        """Execute a high-priority command, using the high-priority slot if available.
        
        This is used for critical operations that should take precedence over 
        other operations, like emergency stop or critical device settings.
        
        Args:
            command: The command name
            **params: Command parameters
            
        Returns:
            Command ID if queued, or direct result if executed immediately
            
        Raises:
            ValueError: If the command is not supported by the device
        """
        return await self._execute_command_internal(command, True, **params)

    async def _execute_command_internal(self, command: str, high_priority: bool, **params) -> Any:
        """Internal method to execute commands with priority options.
        
        Args:
            command: The command name
            high_priority: Whether to execute as high priority
            **params: Command parameters
            
        Returns:
            Command ID if queued, or direct result if executed immediately
            
        Raises:
            ValueError: If the command is not supported by the device
        """
        if not self._command_queue:
            # Direct execution if no queue available
            _LOGGER.debug(f"Executing {command} directly (no queue available)")
            method = getattr(self, f"set_{command}", None)
            if not method:
                method = getattr(self.api, f"set_{command}", None)
                if not method:
                    raise ValueError(f"Command '{command}' not supported by device {self.serial}")
                
            # Use task manager if available
            if self._task_manager:
                return await self._task_manager.run_task(method(**params), "high" if high_priority else "normal")
            else:
                return await method(**params)
            
        # Add to queue with appropriate priority
        priority = 10 if high_priority else 0  # Use higher number for higher priority
        _LOGGER.debug(f"Queueing command {command} for device {self.serial} with priority {priority}")
        cmd_id = await self._command_queue.async_add_command(
            self.serial, command, params=params, priority=priority
        )
        return cmd_id

    def is_attribute_cached(self, attribute: str) -> bool:
        """Check if an attribute's value comes from cache.
        
        Args:
            attribute: The attribute name
            
        Returns:
            True if the attribute value comes from cache, False otherwise
        """
        return attribute in self._cached_attributes

    def is_attribute_stale(self, attribute: str, max_age_seconds: int = DEFAULT_CACHE_MAX_AGE) -> bool:
        """Check if an attribute's cached value is stale.
        
        Args:
            attribute: The attribute name
            max_age_seconds: Maximum age in seconds before considered stale
            
        Returns:
            True if the attribute is stale, False otherwise
        """
        if attribute not in self._cached_attributes:
            return False
            
        age = time.time() - self._cached_attributes[attribute]
        return age > max_age_seconds

    @property
    def serial(self) -> str:
        return cast(str, self._data.get("deviceSn"))

    @property
    def model(self) -> str:
        return cast(str, self._data.get("productIdentifier"))

    @property
    def model_name(self) -> str:
        return cast(str, self._data.get("productName"))

    @property
    def name(self) -> str:
        return cast(str, self._data.get("name"))

    @property
    def mac(self) -> str:
        return cast(str, self._data.get("mac"))

    @property
    def software_version(self) -> str:
        return cast(str, self._data.get("softwareVersion"))

    @property
    def hardware_version(self) -> str:
        return cast(str, self._data.get("hardwareVersion"))

    @property
    def connection_state(self) -> str:
        """Return the connection state of the device."""
        return self._connection_state
        
    @property
    def data_freshness(self) -> str:
        """Return the freshness of device data.
        
        Returns one of:
        - "live": All data is from live API
        - "cached": Data is from cache but not stale
        - "stale": Data is from cache and stale
        - "partial_live": Mix of live and cached data
        """
        if not self._cached_attributes:
            return FRESHNESS_LIVE
            
        # If more than half of attributes are from cache
        if len(self._cached_attributes) > len(self._data) / 2:
            # If any of the cached attributes are older than 1 hour
            now = time.time()
            if any((now - timestamp) > DEFAULT_CACHE_MAX_AGE for timestamp in self._cached_attributes.values()):
                return FRESHNESS_STALE
            return FRESHNESS_CACHED
        
        return FRESHNESS_PARTIAL_LIVE
        
    @property
    def available(self) -> bool:
        """Return if the device is available.
        
        A device is considered available if we have any data, either live or cached.
        """
        return bool(self._data)
        
    @property
    def last_updated(self) -> float:
        """Return the timestamp of the last successful update."""
        return self._last_update_time


# Maintain backward compatibility
class Device(EnhancedDevice):
    """Legacy Device class for backward compatibility."""
    pass
