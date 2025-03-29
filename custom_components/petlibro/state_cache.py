"""PetLibro device state cache with persistence and compression."""
import asyncio
import gzip
import json
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PetLibroStateCache:
    """Cache for PetLibro device state with background saving and compression."""

    def __init__(self, hass: HomeAssistant, config_entry_id: str):
        """Initialize the cache.

        Args:
            hass: HomeAssistant instance
            config_entry_id: The config entry ID this cache is associated with
        """
        self.hass = hass
        self.config_entry_id = config_entry_id
        self.cache_file = os.path.join(
            hass.config.path(), f"petlibro_cache_{config_entry_id}.json.gz"
        )
        self.data: Dict[str, Dict[str, Any]] = {}
        self.last_save = 0
        self.save_interval = 300  # 5 minutes
        self.dirty = False
        self._lock = asyncio.Lock()

        # Schedule initial cache load
        self.hass.async_create_task(self.async_load_cache())

    async def async_load_cache(self) -> None:
        """Load cache from file in background."""
        async with self._lock:
            def _load_file() -> Dict[str, Any]:
                """Load cache file from disk (runs in executor)."""
                if not os.path.exists(self.cache_file):
                    return {}

                try:
                    with gzip.open(self.cache_file, "rt") as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError, gzip.BadGzipFile) as err:
                    _LOGGER.error("Failed to load cache from %s: %s", self.cache_file, err)
                    
                    # Try to recover from uncompressed file if exists
                    uncompressed_file = self.cache_file.replace(".gz", "")
                    if os.path.exists(uncompressed_file):
                        try:
                            _LOGGER.info("Attempting to load from uncompressed backup %s", uncompressed_file)
                            with open(uncompressed_file, "r") as f:
                                return json.load(f)
                        except (json.JSONDecodeError, IOError) as err2:
                            _LOGGER.error("Failed to load uncompressed cache: %s", err2)
                
                return {}

            # Load file in executor to avoid blocking
            self.data = await self.hass.async_add_executor_job(_load_file)
            _LOGGER.debug("Loaded cache with %d devices", len(self.data))

    async def async_save_cache(self) -> None:
        """Save cache to file in background."""
        if not self.dirty:
            return

        async with self._lock:
            def _save_file(data: Dict[str, Any]) -> None:
                """Save cache file to disk (runs in executor)."""
                try:
                    # Save to temp file first
                    temp_file = f"{self.cache_file}.tmp"
                    
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

                    with gzip.open(temp_file, "wt") as f:
                        json.dump(data, f)
                    
                    # Also save uncompressed backup
                    uncompressed_file = self.cache_file.replace(".gz", "")
                    with open(uncompressed_file, "w") as f:
                        json.dump(data, f)
                    
                    # Replace the actual file (atomic operation)
                    os.replace(temp_file, self.cache_file)
                    
                    _LOGGER.debug("Cache saved to %s", self.cache_file)
                except (IOError, gzip.BadGzipFile) as err:
                    _LOGGER.error("Failed to save cache to %s: %s", self.cache_file, err)

            # Save file in executor to avoid blocking
            await self.hass.async_add_executor_job(_save_file, self.data)
            self.last_save = time.time()
            self.dirty = False

    async def _background_save_loop(self) -> None:
        """Background task that periodically saves the cache."""
        while True:
            # Check if save is needed
            if self.dirty and (time.time() - self.last_save) >= self.save_interval:
                await self.async_save_cache()
            
            # Sleep for a while (shorter interval for quicker response)
            await asyncio.sleep(60)  # Check every minute

    def get_device_state(self, device_id: str) -> Dict[str, Any]:
        """Get cached state for a device.
        
        Args:
            device_id: The device ID
            
        Returns:
            The cached device state or empty dict if not found
        """
        return self.data.get(device_id, {}).get("state", {})

    def get_attribute(
        self, device_id: str, attribute: str, max_age_seconds: Optional[int] = None
    ) -> Tuple[Any, bool]:
        """Get an attribute with freshness check.
        
        Args:
            device_id: The device ID
            attribute: The attribute name
            max_age_seconds: Maximum age in seconds for the attribute to be considered fresh
            
        Returns:
            Tuple of (attribute_value, is_fresh) where is_fresh indicates if data is within max_age
        """
        device_data = self.data.get(device_id, {})
        state = device_data.get("state", {})
        timestamps = device_data.get("timestamps", {})
        
        # Check if attribute exists
        if attribute not in state:
            return None, False
        
        # Get attribute value and timestamp
        value = state.get(attribute)
        timestamp = timestamps.get(attribute, 0)
        
        # Check if attribute is fresh
        is_fresh = True
        if max_age_seconds is not None:
            age = time.time() - timestamp
            is_fresh = age <= max_age_seconds
            
        return value, is_fresh

    def update_device_state(self, device_id: str, state: Dict[str, Any]) -> None:
        """Update cached state for a device.
        
        Args:
            device_id: The device ID
            state: The new device state
        """
        # Initialize device in cache if needed
        if device_id not in self.data:
            self.data[device_id] = {"state": {}, "timestamps": {}}
            
        # Update state values and timestamps
        current_time = time.time()
        for key, value in state.items():
            self.data[device_id]["state"][key] = value
            self.data[device_id]["timestamps"][key] = current_time
            
        self.dirty = True

    def update_attribute(self, device_id: str, attribute: str, value: Any) -> None:
        """Update a specific attribute.
        
        Args:
            device_id: The device ID
            attribute: The attribute name
            value: The new attribute value
        """
        # Initialize device in cache if needed
        if device_id not in self.data:
            self.data[device_id] = {"state": {}, "timestamps": {}}
            
        # Update attribute value and timestamp
        self.data[device_id]["state"][attribute] = value
        self.data[device_id]["timestamps"][attribute] = time.time()
        
        self.dirty = True

    def clear_cache(self) -> None:
        """Clear the cache."""
        self.data = {}
        self.dirty = True

    def is_attribute_stale(
        self, device_id: str, attribute: str, max_age_seconds: int
    ) -> bool:
        """Check if data is stale.
        
        Args:
            device_id: The device ID
            attribute: The attribute name
            max_age_seconds: Maximum age in seconds before considered stale
            
        Returns:
            True if attribute is stale or not found, False otherwise
        """
        device_data = self.data.get(device_id, {})
        state = device_data.get("state", {})
        timestamps = device_data.get("timestamps", {})
        
        # Check if attribute exists
        if attribute not in state or attribute not in timestamps:
            return True
            
        # Check age
        age = time.time() - timestamps.get(attribute, 0)
        return age > max_age_seconds
        
    def clean_stale_data(self, max_age_seconds: int) -> int:
        """Remove stale data from cache.
        
        Args:
            max_age_seconds: Maximum age in seconds before data is removed
            
        Returns:
            Number of attributes cleaned
        """
        cleaned_count = 0
        current_time = time.time()
        
        for device_id, device_data in list(self.data.items()):
            timestamps = device_data.get("timestamps", {})
            state = device_data.get("state", {})
            
            # Find stale attributes
            stale_attrs = []
            for attr, timestamp in list(timestamps.items()):
                if (current_time - timestamp) > max_age_seconds:
                    stale_attrs.append(attr)
                    
            # Remove stale attributes
            for attr in stale_attrs:
                if attr in state:
                    del state[attr]
                if attr in timestamps:
                    del timestamps[attr]
                cleaned_count += 1
                
            # Remove device if it has no attributes left
            if not state:
                del self.data[device_id]
                
        if cleaned_count > 0:
            self.dirty = True
            
        return cleaned_count
        
    def start_background_save(self) -> None:
        """Start the background save loop."""
        self.hass.async_create_task(self._background_save_loop())