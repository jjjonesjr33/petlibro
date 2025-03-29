"""Tests for the PetLibro notification manager."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import time

from custom_components.petlibro.notification_manager import NotificationManager

async def test_notify_connection_change():
    """Test connection change notifications."""
    hass = MagicMock()
    manager = NotificationManager(hass, "test_entry_id", {
        "notify_connection_offline": True,
        "notify_connection_restored": True
    })
    
    # Patch _send_notification
    with patch.object(manager, '_send_notification') as mock_send:
        # Test offline notification
        await manager.notify_connection_change("offline", "online")
        mock_send.assert_called_once()
        assert "Connection Lost" in mock_send.call_args[1]["title"]
        
        mock_send.reset_mock()
        
        # Test restored notification
        await manager.notify_connection_change("online", "offline")
        mock_send.assert_called_once()
        assert "Connection Restored" in mock_send.call_args[1]["title"]

async def test_notify_command_status():
    """Test command status notifications."""
    hass = MagicMock()
    manager = NotificationManager(hass, "test_entry_id", {
        "notify_commands_queued": True,
        "notify_commands_executed": True,
        "notify_commands_failed": True
    })
    
    # Patch _send_notification
    with patch.object(manager, '_send_notification') as mock_send:
        # Test queued notification
        await manager.notify_command_queued("manual_feed", "MyFeeder", "API offline")
        mock_send.assert_called_once()
        assert "Command Queued" in mock_send.call_args[1]["title"]
        
        mock_send.reset_mock()
        
        # Test executed notification
        await manager.notify_command_executed("manual_feed", "MyFeeder", True)
        mock_send.assert_called_once()
        assert "Command Executed" in mock_send.call_args[1]["title"]
        
        mock_send.reset_mock()
        
        # Test failed notification
        await manager.notify_command_failed("manual_feed", "MyFeeder", "API error", 3)
        mock_send.assert_called_once()
        assert "Command Failed" in mock_send.call_args[1]["title"]
        assert "3 retries" in mock_send.call_args[0][0]

async def test_notification_cooldown():
    """Test notification cooldown logic."""
    hass = MagicMock()
    manager = NotificationManager(hass, "test_entry_id", {
        "notification_cooldown": 60  # 1 minute cooldown
    })
    
    # Patch _send_notification
    with patch.object(manager, '_send_notification') as mock_send:
        # First notification should go through
        await manager.notify_connection_change("offline")
        assert mock_send.call_count == 1
        
        # Second immediate notification should be suppressed
        await manager.notify_connection_change("offline")
        assert mock_send.call_count == 1
        
        # Manually bypass cooldown
        manager.last_notification_time["connection"] = time.time() - 61
        
        # Now the notification should go through again
        await manager.notify_connection_change("offline")
        assert mock_send.call_count == 2

async def test_critical_state_notifications():
    """Test critical state notifications."""
    hass = MagicMock()
    manager = NotificationManager(hass, "test_entry_id", {
        "notify_critical_battery": True,
        "notify_critical_water_level": True,
        "notify_critical_food_level": True
    })
    
    # Patch _send_notification
    with patch.object(manager, '_send_notification') as mock_send:
        # Test battery notification
        await manager.notify_critical_state("MyFeeder", "battery", 15)
        mock_send.assert_called_once()
        assert "Battery Alert" in mock_send.call_args[1]["title"]
        
        mock_send.reset_mock()
        
        # Test water level notification
        await manager.notify_critical_state("MyFeeder", "water_level", 10)
        mock_send.assert_called_once()
        assert "Water Level Alert" in mock_send.call_args[1]["title"]
        
        mock_send.reset_mock()
        
        # Test food level notification
        await manager.notify_critical_state("MyFeeder", "food_level", 15)
        mock_send.assert_called_once()
        assert "Food Level Alert" in mock_send.call_args[1]["title"]
        
        mock_send.reset_mock()
        
        # Test non-critical level (should not send notification)
        await manager.notify_critical_state("MyFeeder", "battery", 50)
        mock_send.assert_not_called()

async def test_event_handlers():
    """Test the event handlers."""
    hass = MagicMock()
    manager = NotificationManager(hass, "test_entry_id")
    
    # Patch notification methods
    with patch.object(manager, 'notify_connection_change') as mock_conn, \
         patch.object(manager, 'notify_command_queued') as mock_queued, \
         patch.object(manager, 'notify_command_executed') as mock_executed, \
         patch.object(manager, 'notify_command_failed') as mock_failed, \
         patch.object(manager, 'notify_critical_state') as mock_critical:
        
        # Test connection change event
        event = MagicMock()
        event.data = {
            "state": "offline",
            "previous_state": "online",
            "device_name": "MyFeeder"
        }
        await manager._handle_connection_change(event)
        mock_conn.assert_called_once_with("offline", "online", "MyFeeder")
        
        # Test command queued event
        event.data = {
            "command": "manual_feed",
            "device_name": "MyFeeder",
            "status": "queued",
            "reason": "API offline"
        }
        await manager._handle_command_status(event)
        mock_queued.assert_called_once_with("manual_feed", "MyFeeder", "API offline")
        
        # Test command executed event
        event.data = {
            "command": "manual_feed",
            "device_name": "MyFeeder",
            "status": "completed",
            "was_queued": True
        }
        await manager._handle_command_status(event)
        mock_executed.assert_called_once_with("manual_feed", "MyFeeder", True)
        
        # Test command failed event
        event.data = {
            "command": "manual_feed",
            "device_name": "MyFeeder",
            "status": "failed",
            "reason": "API error",
            "retries": 3
        }
        await manager._handle_command_status(event)
        mock_failed.assert_called_once_with("manual_feed", "MyFeeder", "API error", 3)
        
        # Test device state event
        event.data = {
            "device_name": "MyFeeder",
            "battery": 15
        }
        await manager._handle_device_state(event)
        mock_critical.assert_called_once_with("MyFeeder", "battery", 15)