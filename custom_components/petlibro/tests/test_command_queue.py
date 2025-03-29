"""Tests for the PetLibro command queue."""
import asyncio
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from homeassistant.core import HomeAssistant
from ..command_queue import CommandQueue, CommandEntry


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config.path.return_value = "/tmp/petlibro_test"
    
    # Mock async_add_executor_job to run synchronously for testing
    async def mock_executor(func, *args, **kwargs):
        return func(*args, **kwargs)
    
    hass.async_add_executor_job.side_effect = mock_executor
    
    # Mock async_create_task to run tasks immediately
    async def mock_create_task(coro):
        return await coro
    
    hass.async_create_task.side_effect = mock_create_task
    
    return hass


@pytest.fixture
def mock_hub():
    """Create a mock hub instance."""
    hub = MagicMock()
    hub.config_entry_id = "test_entry_id"
    
    # Mock API with connection state
    api = MagicMock()
    api.session = MagicMock()
    api.session.connection_state = "online"
    hub.api = api
    
    # Mock get_device method
    async def mock_get_device(device_id):
        device = MagicMock()
        device.serial = device_id
        return device
    
    hub.get_device.side_effect = mock_get_device
    
    return hub


@pytest.fixture
def command_queue(mock_hass, mock_hub):
    """Create a CommandQueue instance for testing."""
    queue = CommandQueue(mock_hass, mock_hub)
    
    # Patch _load_queue to avoid file operations
    async def mock_load_queue():
        queue.queue = []
    
    queue._load_queue = mock_load_queue
    
    # Patch _save_queue to avoid file operations
    async def mock_save_queue():
        queue.dirty = False
        queue.last_save = datetime.now().timestamp()
    
    queue._save_queue = mock_save_queue
    
    return queue


async def test_command_entry_creation():
    """Test CommandEntry initialization."""
    entry = CommandEntry(
        device_id="test_device",
        command="test_command",
        params={"param1": "value1"},
        priority=5
    )
    
    assert entry.device_id == "test_device"
    assert entry.command == "test_command"
    assert entry.params == {"param1": "value1"}
    assert entry.priority == 5
    assert entry.status == "pending"
    assert entry.retries == 0
    assert entry.max_retries == 5


async def test_command_entry_serialization():
    """Test CommandEntry serialization and deserialization."""
    original = CommandEntry(
        device_id="test_device",
        command="test_command",
        params={"param1": "value1"},
        priority=5
    )
    
    # Set some additional properties
    original.retries = 2
    original.status = "failed"
    original.error = "Test error"
    
    # Serialize to JSON
    json_data = original.to_json()
    
    # Deserialize from JSON
    deserialized = CommandEntry.from_json(json_data)
    
    # Check that properties match
    assert deserialized.id == original.id
    assert deserialized.device_id == original.device_id
    assert deserialized.command == original.command
    assert deserialized.params == original.params
    assert deserialized.priority == original.priority
    assert deserialized.retries == original.retries
    assert deserialized.status == original.status
    assert deserialized.error == original.error


async def test_add_command(command_queue):
    """Test adding a command to the queue."""
    # Add a command
    cmd_id = await command_queue.async_add_command(
        device_id="test_device",
        command="test_command",
        params={"param1": "value1"},
        priority=5
    )
    
    # Verify command was added
    assert len(command_queue.queue) == 1
    assert command_queue.queue[0].id == cmd_id
    assert command_queue.queue[0].device_id == "test_device"
    assert command_queue.queue[0].command == "test_command"
    assert command_queue.queue[0].params == {"param1": "value1"}
    assert command_queue.queue[0].priority == 5
    assert command_queue.queue[0].status == "pending"


async def test_command_execution(command_queue, mock_hub):
    """Test command execution."""
    # Setup a mock device method
    test_device = await mock_hub.get_device("test_device")
    test_device.set_test_command = MagicMock()
    
    async def mock_method(**kwargs):
        return "success"
    
    test_device.set_test_command.side_effect = mock_method
    
    # Add a command
    cmd_id = await command_queue.async_add_command(
        device_id="test_device",
        command="test_command",
        params={"param1": "value1"}
    )
    
    # Process the queue
    await command_queue.async_process_queue()
    
    # Verify command was executed
    test_device.set_test_command.assert_called_once_with(param1="value1")
    
    # Check command status
    status = command_queue.get_command_status(cmd_id)
    assert status["status"] == "completed"


async def test_command_execution_api_offline(command_queue, mock_hub):
    """Test command behavior when API is offline."""
    # Set API to offline
    mock_hub.api.session.connection_state = "offline"
    
    # Add a command
    cmd_id = await command_queue.async_add_command(
        device_id="test_device",
        command="test_command"
    )
    
    # Process the queue
    await command_queue.async_process_queue()
    
    # Command should remain in the queue since API is offline
    assert len(command_queue.queue) == 1
    assert command_queue.queue[0].status == "pending"
    
    # Set API back to online
    mock_hub.api.session.connection_state = "online"
    
    # Setup a mock device method
    test_device = await mock_hub.get_device("test_device")
    test_device.set_test_command = MagicMock()
    
    async def mock_method(**kwargs):
        return "success"
    
    test_device.set_test_command.side_effect = mock_method
    
    # Process the queue again
    await command_queue.async_process_queue()
    
    # Verify command was executed now
    test_device.set_test_command.assert_called_once()
    
    # Check command status
    status = command_queue.get_command_status(cmd_id)
    assert status["status"] == "completed"


async def test_command_retries(command_queue, mock_hub):
    """Test command retry behavior on failure."""
    # Setup a mock device method that fails
    test_device = await mock_hub.get_device("test_device")
    test_device.set_test_command = MagicMock()
    
    # Set up the method to fail on first call and succeed on second
    call_count = 0
    
    async def mock_method(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Test failure")
        return "success"
    
    test_device.set_test_command.side_effect = mock_method
    
    # Add a command
    cmd_id = await command_queue.async_add_command(
        device_id="test_device",
        command="test_command"
    )
    
    # Process the queue - first attempt should fail
    await command_queue.async_process_queue()
    
    # Check that it's pending retry
    assert command_queue.queue[0].status == "pending"
    assert command_queue.queue[0].retries == 1
    
    # Reset next_retry_time to force immediate retry for testing
    command_queue.queue[0].next_retry_time = None
    
    # Process the queue again - should succeed this time
    await command_queue.async_process_queue()
    
    # Verify command was executed twice
    assert test_device.set_test_command.call_count == 2
    
    # Check command status
    status = command_queue.get_command_status(cmd_id)
    assert status["status"] == "completed"


async def test_command_priority(command_queue):
    """Test command priority ordering."""
    # Add multiple commands with different priorities
    low_priority_id = await command_queue.async_add_command(
        device_id="test_device",
        command="low_priority_command",
        priority=1
    )
    
    medium_priority_id = await command_queue.async_add_command(
        device_id="test_device",
        command="medium_priority_command",
        priority=5
    )
    
    high_priority_id = await command_queue.async_add_command(
        device_id="test_device",
        command="high_priority_command",
        priority=10
    )
    
    # Add mock methods to devices to track execution order
    test_device = await command_queue.hub.get_device("test_device")
    execution_order = []
    
    async def mock_low_priority(**kwargs):
        execution_order.append("low")
        return "success"
    
    async def mock_medium_priority(**kwargs):
        execution_order.append("medium")
        return "success"
    
    async def mock_high_priority(**kwargs):
        execution_order.append("high")
        return "success"
    
    test_device.set_low_priority_command = MagicMock(side_effect=mock_low_priority)
    test_device.set_medium_priority_command = MagicMock(side_effect=mock_medium_priority)
    test_device.set_high_priority_command = MagicMock(side_effect=mock_high_priority)
    
    # Process the queue
    await command_queue.async_process_queue()
    
    # Verify execution order based on priority
    assert execution_order == ["high", "medium", "low"]


async def test_command_cancellation(command_queue):
    """Test cancelling a pending command."""
    # Add a command
    cmd_id = await command_queue.async_add_command(
        device_id="test_device",
        command="test_command"
    )
    
    # Verify command was added
    assert len(command_queue.queue) == 1
    
    # Cancel the command
    result = await command_queue.async_cancel_command(cmd_id)
    
    # Verify command was cancelled
    assert result is True
    assert len(command_queue.queue) == 0
    
    # Try to get status of cancelled command
    status = command_queue.get_command_status(cmd_id)
    assert status is None


async def test_command_callback(command_queue, mock_hub):
    """Test command callbacks."""
    # Setup a callback function
    callback_called = False
    callback_status = None
    
    def callback(cmd):
        nonlocal callback_called, callback_status
        callback_called = True
        callback_status = cmd.status
    
    # Add a command with callback
    cmd_id = await command_queue.async_add_command(
        device_id="test_device",
        command="test_command",
        callback=callback
    )
    
    # Setup a mock device method
    test_device = await mock_hub.get_device("test_device")
    test_device.set_test_command = MagicMock()
    
    async def mock_method(**kwargs):
        return "success"
    
    test_device.set_test_command.side_effect = mock_method
    
    # Process the queue
    await command_queue.async_process_queue()
    
    # Verify callback was called
    assert callback_called is True
    assert callback_status == "completed"