"""
Example demonstrating how to use the adaptive polling coordinator.

This file provides examples of how device methods can register activity
to trigger adaptive polling behavior.
"""
import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant

from ..adaptive_coordinator import AdaptivePollingCoordinator
from ..task_manager import BackgroundTaskManager

_LOGGER = logging.getLogger(__name__)

# Example 1: Basic usage in a device method
async def set_manual_feed(self):
    """Trigger manual feeding, with increased polling after.
    
    This example demonstrates registering activity when a user
    triggers a manual feeding, which should cause more frequent
    polling immediately afterward to show the result.
    """
    # Execute the command
    if self._command_queue:
        await self._command_queue.async_add_command(self.serial, "manual_feed")
    else:
        await self.api.set_manual_feed(self.serial)
    
    # Register activity to increase polling frequency
    if hasattr(self.hub, "coordinator") and hasattr(self.hub.coordinator, "register_activity"):
        self.hub.coordinator.register_activity(self.serial, "manual_feed")
        
    # Force an immediate refresh
    await self.refresh()


# Example 2: Using the hub's convenience method
async def set_feeding_schedule(self, schedule_data):
    """Set a new feeding schedule with adaptive polling.
    
    This example demonstrates using the hub's convenience method
    to register device activity.
    """
    # Execute the command
    if self._command_queue:
        await self._command_queue.async_add_command(
            self.serial, "set_feeding_schedule", params={"schedule": schedule_data}
        )
    else:
        await self.api.set_feeding_schedule(self.serial, schedule_data)
    
    # Register activity via the hub's convenience method
    self.hub.register_device_activity(self.serial, "schedule_change")
    
    # Force an immediate refresh
    await self.refresh()


# Example 3: Full adaptive coordinator setup
async def setup_adaptive_polling_example(hass: HomeAssistant):
    """Example showing how to set up an adaptive polling coordinator."""
    # Create a task manager
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    # Define an update method
    async def update_method():
        """Example update method that fetches data."""
        _LOGGER.debug("Fetching data from API...")
        await asyncio.sleep(0.5)  # Simulate API call
        return {"device1": {"status": "online", "battery": 75}}
    
    # Create the adaptive coordinator
    coordinator = AdaptivePollingCoordinator(
        hass,
        _LOGGER,
        name="example_coordinator",
        update_method=update_method,
        min_update_interval=timedelta(seconds=30),
        max_update_interval=timedelta(minutes=10),
        task_manager=task_manager,
    )
    
    # First refresh to initialize data
    await coordinator.async_refresh()
    
    # Register activity (would normally be triggered by user actions)
    coordinator.register_activity("device1", "button_press")
    
    # Later, get statistics about the polling behavior
    stats = coordinator.get_statistics()
    _LOGGER.info("Adaptive polling statistics: %s", stats)
    
    # Manually adjust update interval temporarily
    await coordinator.async_adjust_update_interval(timedelta(seconds=15))
    
    # Cleanup when done
    await task_manager.async_stop()


# Example 4: Integration with sensor/entity updates
class AdaptivePollingEntity:
    """Example entity that integrates with adaptive polling.
    
    This demonstrates how an entity can detect important state
    changes and register activity accordingly.
    """
    
    def __init__(self, device_id, coordinator):
        """Initialize the entity."""
        self._device_id = device_id
        self.coordinator = coordinator
        self._attr_native_value = None
        self._last_value = None
    
    async def async_update(self):
        """Update the entity state.
        
        This method demonstrates detecting important state changes and
        registering device activity to increase polling frequency.
        """
        # Get updated data from the coordinator
        data = self.coordinator.data.get(self._device_id, {})
        
        # Get the new value
        new_value = data.get("battery", 0)
        
        # Check if this is an important change that should trigger more frequent polling
        if self._last_value is not None:
            # Example: If battery level drops by more than 10%, consider it important
            if new_value < self._last_value - 10:
                self.coordinator.register_activity(
                    self._device_id, "significant_battery_drop"
                )
                _LOGGER.debug(
                    "Registered activity due to battery drop: %s → %s",
                    self._last_value,
                    new_value
                )
        
        # Update state values
        self._attr_native_value = new_value
        self._last_value = new_value