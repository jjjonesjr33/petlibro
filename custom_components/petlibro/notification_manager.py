"""PetLibro notification manager for mobile alerts during outages."""
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class NotificationManager:
    """Manager for PetLibro notifications."""
    
    def __init__(self, hass: HomeAssistant, entry_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the notification manager."""
        self.hass = hass
        self.entry_id = entry_id
        self.config = config or {}
        self.history = []
        self.last_notification_time = {}  # Track when we last sent notifications by type
        self.notification_cooldown = 300  # Default 5 minutes between similar notifications
    
    async def async_setup(self):
        """Set up the notification manager."""
        # Register event listeners for important events
        self.hass.bus.async_listen("petlibro_connection_change", self._handle_connection_change)
        self.hass.bus.async_listen("petlibro_command_status", self._handle_command_status)
        self.hass.bus.async_listen("petlibro_device_state", self._handle_device_state)
        
        return True
        
    async def notify_connection_change(self, state, previous_state=None, device_name=None):
        """Notify about connection state changes."""
        if not self._should_notify("connection"):
            return
            
        message = f"PetLibro API connection changed to: {state}"
        if device_name:
            message = f"{device_name}: {message}"
            
        if state == "offline" and self.config.get("notify_connection_offline", True):
            await self._send_notification(
                message,
                title="PetLibro Connection Lost",
                notification_id=f"petlibro_connection_{device_name or 'api'}",
                importance="high"
            )
        elif state == "online" and previous_state == "offline" and self.config.get("notify_connection_restored", True):
            await self._send_notification(
                message,
                title="PetLibro Connection Restored",
                notification_id=f"petlibro_connection_{device_name or 'api'}",
                importance="normal"
            )
        
        self._update_notification_time("connection")

    async def notify_command_queued(self, command, device_name, reason=None):
        """Notify about commands queued during outages."""
        if not self._should_notify("command_queued"):
            return
            
        message = f"Command '{command}' queued for {device_name}"
        if reason:
            message += f" ({reason})"
            
        if self.config.get("notify_commands_queued", True):
            await self._send_notification(
                message,
                title="PetLibro Command Queued",
                notification_id=f"petlibro_command_{command}_{device_name}",
                importance="normal"
            )
        
        self._update_notification_time("command_queued")

    async def notify_command_executed(self, command, device_name, was_queued=False):
        """Notify about commands that executed after being queued."""
        if not self._should_notify("command_executed") or not was_queued:
            return
            
        message = f"Queued command '{command}' executed for {device_name}"
            
        if self.config.get("notify_commands_executed", True):
            await self._send_notification(
                message,
                title="PetLibro Command Executed",
                notification_id=f"petlibro_command_{command}_{device_name}",
                importance="normal"
            )
        
        self._update_notification_time("command_executed")

    async def notify_command_failed(self, command, device_name, reason=None, retries=0):
        """Notify about commands that failed permanently."""
        if not self._should_notify("command_failed"):
            return
            
        message = f"Command '{command}' failed for {device_name}"
        if reason:
            message += f": {reason}"
        if retries > 0:
            message += f" after {retries} retries"
            
        if self.config.get("notify_commands_failed", True):
            await self._send_notification(
                message,
                title="PetLibro Command Failed",
                notification_id=f"petlibro_command_{command}_{device_name}",
                importance="high"
            )
        
        self._update_notification_time("command_failed")

    async def notify_critical_state(self, device_name, state_type, state_value):
        """Notify about critical device states."""
        if not self._should_notify(f"critical_state_{state_type}"):
            return
        
        # Define critical states that should trigger notifications
        critical_states = {
            "battery": lambda x: x < 20,  # Battery below 20%
            "water_level": lambda x: x < 15,  # Water level below 15%
            "food_level": lambda x: x < 20,  # Food level below 20%
        }
        
        if state_type in critical_states and critical_states[state_type](state_value):
            message = f"{device_name} {state_type} is at {state_value}%"
            
            if self.config.get(f"notify_critical_{state_type}", True):
                await self._send_notification(
                    message,
                    title=f"PetLibro {state_type.replace('_', ' ').title()} Alert",
                    notification_id=f"petlibro_{state_type}_{device_name}",
                    importance="high"
                )
            
            self._update_notification_time(f"critical_state_{state_type}")

    async def _send_notification(self, message, title=None, notification_id=None, importance="normal"):
        """Send a notification to the user."""
        # Add to history
        entry = {
            "message": message,
            "title": title,
            "timestamp": time.time(),
            "importance": importance
        }
        self.history.append(entry)
        
        # Trim history if it gets too long
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        # Send notification via Home Assistant
        data = {
            "title": title or "PetLibro Notification",
            "message": message,
            "data": {
                "notification_id": notification_id or f"petlibro_{int(time.time())}",
                "importance": importance,
                "tag": "petlibro"
            }
        }
        
        # Add actions if this is a command notification
        if "command" in (notification_id or ""):
            data["data"]["actions"] = [
                {
                    "action": "VIEW_COMMANDS",
                    "title": "View Queue",
                    "uri": f"/lovelace/petlibro?command_queue=open"
                }
            ]
        
        # Use persistent notification service within Home Assistant
        await self.hass.services.async_call("persistent_notification", "create", data)
        
        # Also use mobile notification if configured
        if self.config.get("use_mobile_notifications", False):
            service = self.config.get("notification_service", "notify.mobile_app")
            if service.startswith("notify."):
                try:
                    await self.hass.services.async_call(
                        service.split(".", 1)[0],
                        service.split(".", 1)[1],
                        data
                    )
                except Exception as ex:
                    _LOGGER.error(f"Failed to send mobile notification: {ex}")

    def _should_notify(self, notification_type):
        """Check if we should send a notification based on cooldown."""
        now = time.time()
        last_time = self.last_notification_time.get(notification_type, 0)
        cooldown = self.config.get(f"{notification_type}_cooldown", self.notification_cooldown)
        
        return (now - last_time) > cooldown

    def _update_notification_time(self, notification_type):
        """Update the last notification time for this type."""
        self.last_notification_time[notification_type] = time.time()

    def get_history(self, limit=10):
        """Get notification history."""
        return sorted(self.history, key=lambda x: x["timestamp"], reverse=True)[:limit]
        
    async def _handle_connection_change(self, event):
        """Handle connection state change events."""
        data = event.data
        await self.notify_connection_change(
            data.get("state"),
            data.get("previous_state"),
            data.get("device_name")
        )

    async def _handle_command_status(self, event):
        """Handle command status change events."""
        data = event.data
        command = data.get("command")
        device_name = data.get("device_name")
        status = data.get("status")
        
        if status == "queued":
            await self.notify_command_queued(
                command,
                device_name,
                data.get("reason")
            )
        elif status == "completed":
            await self.notify_command_executed(
                command,
                device_name,
                data.get("was_queued", False)
            )
        elif status == "failed":
            await self.notify_command_failed(
                command,
                device_name,
                data.get("reason"),
                data.get("retries", 0)
            )

    async def _handle_device_state(self, event):
        """Handle device state change events."""
        data = event.data
        device_name = data.get("device_name")
        
        # Check for critical states
        for state_type in ["battery", "water_level", "food_level"]:
            if state_type in data:
                await self.notify_critical_state(
                    device_name,
                    state_type,
                    data.get(state_type)
                )