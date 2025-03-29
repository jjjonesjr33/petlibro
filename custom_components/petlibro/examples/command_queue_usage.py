"""
Example usage of the PetLibro command queue system.

This file demonstrates how to use the command queue system to reliably
control PetLibro devices during API outages.

Three approaches are shown:
1. Direct usage through the hub
2. Integration in entity services
3. Future device class integration suggestions
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import STATE_ON, STATE_OFF

from ..entity import PetLibroEntity
from ..hub import PetLibroHub

_LOGGER = logging.getLogger(__name__)

########################
# 1. Direct Hub Usage
########################

async def example_queue_command_via_hub(hub: PetLibroHub, device_id: str) -> str:
    """Example for directly queueing a command through the hub.
    
    Args:
        hub: The PetLibro hub
        device_id: The device ID
    
    Returns:
        The ID of the queued command
    """
    # Queue a command, optionally with parameters
    command_id = await hub.async_add_command(
        device_id=device_id,
        command="manual_feed",
        params={"feed_value": 1},
        priority=10  # Higher priority
    )
    
    # Get status of the command
    status = hub.get_command_status(command_id)
    _LOGGER.debug("Command status: %s", status)
    
    # Get queue statistics
    stats = hub.get_queue_stats()
    _LOGGER.debug("Queue stats: %s", stats)
    
    return command_id

########################
# 2. Entity Integration
########################

class ExamplePetLibroButtonEntity(PetLibroEntity):
    """Example button entity that uses the command queue."""
    
    async def async_press(self) -> None:
        """Press the button."""
        hub = self.coordinator.hub
        device = self.petlibro_device
        
        # Queue a command through the hub
        command_id = await hub.async_add_command(
            device_id=device.serial,
            command="manual_feed"
        )
        
        _LOGGER.debug("Queued manual feed command: %s", command_id)

class ExamplePetLibroSwitchEntity(PetLibroEntity):
    """Example switch entity that uses the command queue."""
    
    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.petlibro_device.feeding_plan
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        hub = self.coordinator.hub
        device = self.petlibro_device
        
        # Queue a command with a callback that handles state update
        await hub.async_add_command(
            device_id=device.serial,
            command="feeding_plan",
            params={"value": True},
            callback=self._handle_command_result
        )
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        hub = self.coordinator.hub
        device = self.petlibro_device
        
        # Queue a command with a callback that handles state update
        await hub.async_add_command(
            device_id=device.serial,
            command="feeding_plan",
            params={"value": False},
            callback=self._handle_command_result
        )
    
    def _handle_command_result(self, cmd):
        """Handle the result of a command."""
        if cmd.status == "completed":
            # Force a refresh when command completes
            self.hass.async_create_task(self.coordinator.async_request_refresh())
        elif cmd.status == "failed":
            _LOGGER.error("Command failed: %s", cmd.error)

########################
# 3. Service Handler
########################

async def handle_service_call(hass: HomeAssistant, hub: PetLibroHub, call: ServiceCall) -> None:
    """Example service call handler that uses the command queue.
    
    Args:
        hass: The HomeAssistant instance
        hub: The PetLibro hub
        call: The service call data
    """
    device_id = call.data.get("device_id")
    portion_size = call.data.get("portion_size", 1)
    
    if not device_id:
        _LOGGER.error("No device_id provided")
        return
    
    # Queue the command
    command_id = await hub.async_add_command(
        device_id=device_id,
        command="manual_feed",
        params={"feed_value": portion_size}
    )
    
    _LOGGER.debug("Queued manual feed command: %s", command_id)


########################
# FUTURE IMPROVEMENT IDEAS
########################

# Future Device Class Implementation Suggestions:
#
# 1. Add a base method to the Device class:
#
# class Device(Event):
#     # ... existing code ...
#     
#     async def _execute_command(self, command: str, **params) -> Any:
#         # Execute a command or queue it if API is offline.
#         #
#         # Args:
#         #     command: The command name without the 'set_' prefix
#         #     **params: Command parameters
#         #     
#         # Returns:
#         #     Command result if executed immediately, or command ID if queued
#         
#         # Get hub from API (requires API to have a hub attribute)
#         hub = getattr(self.api, 'hub', None)
#         
#         if not hub:
#             # Fallback to direct API call if no hub reference
#             method = getattr(self.api, f"set_{command}", None)
#             if not method:
#                 raise ValueError(f"Command '{command}' not found")
#             return await method(self.serial, **params)
#         
#         # Check API connection state
#         if self.api.session.connection_state == "offline":
#             # Queue the command
#             command_id = await hub.async_add_command(
#                 device_id=self.serial,
#                 command=command,
#                 params=params
#             )
#             return command_id
#         else:
#             # Execute directly
#             method = getattr(self.api, f"set_{command}", None)
#             if not method:
#                 raise ValueError(f"Command '{command}' not found")
#             result = await method(self.serial, **params)
#             return result
#     
#     # Update existing methods to use _execute_command:
#     async def set_manual_feed(self, feed_value=1):
#         result = await self._execute_command("manual_feed", feed_value=feed_value)
#         await self.refresh()
#         return result
#
# 2. Add a hub reference to the API:
#
# def __init__(self, hub, session, ...):
#     self.hub = hub
#     # ... existing code ...
#
# This gives devices a way to access the command queue.