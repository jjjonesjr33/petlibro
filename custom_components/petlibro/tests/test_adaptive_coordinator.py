"""Tests for the adaptive polling coordinator."""
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from homeassistant.core import HomeAssistant

from ..adaptive_coordinator import AdaptivePollingCoordinator
from ..task_manager import BackgroundTaskManager


@pytest.fixture
def mock_hass():
    """Return a mocked Home Assistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def mock_logger():
    """Return a mocked logger."""
    return MagicMock()


@pytest.fixture
def mock_task_manager():
    """Return a mocked task manager."""
    manager = MagicMock(spec=BackgroundTaskManager)
    manager.run_task = AsyncMock()
    return manager


@pytest.fixture
def mock_update_method():
    """Return a mocked update method."""
    return AsyncMock(return_value={"device1": {"online": True}})


async def test_adaptive_coordinator_initialization(mock_hass, mock_logger, mock_update_method):
    """Test initialization of adaptive coordinator."""
    min_interval = timedelta(seconds=30)
    max_interval = timedelta(minutes=10)
    
    coordinator = AdaptivePollingCoordinator(
        mock_hass,
        mock_logger,
        "test_coordinator",
        mock_update_method,
        min_interval,
        max_interval
    )
    
    assert coordinator.min_update_interval == min_interval
    assert coordinator.max_update_interval == max_interval
    assert coordinator.current_interval == max_interval
    assert coordinator.update_method == coordinator._adaptive_update
    

async def test_activity_registration(mock_hass, mock_logger, mock_update_method):
    """Test registering activity affects polling frequency."""
    coordinator = AdaptivePollingCoordinator(
        mock_hass,
        mock_logger,
        "test_coordinator",
        mock_update_method,
        timedelta(seconds=30),
        timedelta(minutes=10)
    )
    
    # Initially should be at max interval
    assert coordinator.current_interval == timedelta(minutes=10)
    
    # Register activity
    coordinator.register_activity("device1", "test_action")
    
    # Should now be at or near min interval
    assert coordinator.current_interval < timedelta(minutes=5)
    
    # Current hour should have a lower multiplier
    current_hour = datetime.now().hour
    assert coordinator.usage_patterns[current_hour] < 1.0


async def test_api_performance_adjustment(mock_hass, mock_logger, mock_update_method):
    """Test API performance affects polling frequency."""
    coordinator = AdaptivePollingCoordinator(
        mock_hass,
        mock_logger,
        "test_coordinator",
        mock_update_method,
        timedelta(seconds=30),
        timedelta(minutes=10)
    )
    
    # Record poor API performance
    for _ in range(10):
        coordinator.record_api_result(False, 1.5)  # Failed requests, slow response
    
    # Success rate should be low
    assert coordinator.api_performance["success_rate"] < 0.5
    
    # Get performance factor - should be > 1.0 for poor performance
    factor = coordinator._get_api_performance_factor()
    assert factor > 1.0
    
    # Record good performance
    for _ in range(20):
        coordinator.record_api_result(True, 0.2)  # Successful requests, fast response
    
    # Success rate should be higher
    assert coordinator.api_performance["success_rate"] > 0.8
    
    # Get performance factor - should be <= 1.0 for good performance
    factor = coordinator._get_api_performance_factor()
    assert factor <= 1.0


async def test_adaptive_update_with_task_manager(mock_hass, mock_logger, mock_update_method, mock_task_manager):
    """Test adaptive update with task manager."""
    coordinator = AdaptivePollingCoordinator(
        mock_hass,
        mock_logger, 
        "test_coordinator",
        mock_update_method,
        timedelta(seconds=30),
        timedelta(minutes=10),
        task_manager=mock_task_manager
    )
    
    # Mock return value for task manager
    mock_task_manager.run_task.return_value = {"device1": {"online": True, "batteryState": 100}}
    
    # First update
    result = await coordinator._adaptive_update()
    
    # Verify task manager was used
    mock_task_manager.run_task.assert_called_once()
    
    # Result should match mock return value
    assert result == {"device1": {"online": True, "batteryState": 100}}
    
    # Second update with changed data
    mock_task_manager.run_task.reset_mock()
    mock_task_manager.run_task.return_value = {"device1": {"online": True, "batteryState": 80}}
    
    result = await coordinator._adaptive_update()
    
    # Important change should be detected and activity registered
    assert coordinator.activity_counter > 0


async def test_detect_important_changes(mock_hass, mock_logger, mock_update_method):
    """Test detection of important changes."""
    coordinator = AdaptivePollingCoordinator(
        mock_hass,
        mock_logger,
        "test_coordinator",
        mock_update_method,
        timedelta(seconds=30),
        timedelta(minutes=10)
    )
    
    # Initial data (first result is always important)
    initial_data = {"device1": {"online": True, "batteryState": 100}}
    assert coordinator._detect_important_changes(initial_data) is True
    
    # Same data - should not be important
    same_data = {"device1": {"online": True, "batteryState": 100}}
    assert coordinator._detect_important_changes(same_data) is False
    
    # Changed important attribute
    changed_data = {"device1": {"online": False, "batteryState": 100}}
    assert coordinator._detect_important_changes(changed_data) is True
    
    # Changed unimportant attribute
    unimportant_change = {"device1": {"online": False, "batteryState": 100, "lastSeen": "now"}}
    assert coordinator._detect_important_changes(unimportant_change) is False
    
    # New device appeared
    new_device = {
        "device1": {"online": False, "batteryState": 100},
        "device2": {"online": True, "batteryState": 90}
    }
    assert coordinator._detect_important_changes(new_device) is True


async def test_adjust_polling_frequency(mock_hass, mock_logger, mock_update_method):
    """Test polling frequency adjustment logic."""
    coordinator = AdaptivePollingCoordinator(
        mock_hass,
        mock_logger,
        "test_coordinator",
        mock_update_method,
        timedelta(seconds=30),
        timedelta(minutes=10)
    )
    
    # Initially max interval
    assert coordinator.current_interval == timedelta(minutes=10)
    
    # Set recent activity
    coordinator.last_activity_time = time.time()
    coordinator._adjust_polling_frequency()
    
    # Should be much lower due to recent activity
    assert coordinator.current_interval < timedelta(minutes=5)
    
    # Set activity to be older (5+ minutes ago)
    coordinator.last_activity_time = time.time() - 400
    coordinator._adjust_polling_frequency()
    
    # Should be higher due to older activity
    assert coordinator.current_interval > timedelta(minutes=5)


async def test_temporary_interval_adjustment(mock_hass, mock_logger, mock_update_method):
    """Test manually adjusting update interval temporarily."""
    # Mock asyncio.sleep and asyncio.create_task to avoid actually waiting
    with patch('asyncio.sleep', new=AsyncMock()), \
         patch('asyncio.create_task', new=MagicMock()):
        coordinator = AdaptivePollingCoordinator(
            mock_hass,
            mock_logger,
            "test_coordinator",
            mock_update_method,
            timedelta(seconds=30),
            timedelta(minutes=10)
        )
        
        # Remember original interval
        original_interval = coordinator.update_interval
        
        # Temporarily adjust to 15 seconds
        new_interval = timedelta(seconds=15)
        await coordinator.async_adjust_update_interval(new_interval)
        
        # Verify interval was changed
        assert coordinator.update_interval == new_interval
        
        # In a real scenario, asyncio.create_task would have been called with a function
        # that would eventually restore the adaptive polling interval