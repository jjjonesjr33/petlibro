"""Tests for the BackgroundTaskManager."""
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant

from ..task_manager import BackgroundTaskManager, _TaskGroup


@pytest.fixture
def hass():
    """Fixture for HomeAssistant instance."""
    hass_mock = MagicMock(spec=HomeAssistant)
    
    # Mock async_create_task to actually run the coroutine
    async def async_create_task(coro):
        task = asyncio.create_task(coro)
        return task
    
    hass_mock.async_create_task.side_effect = async_create_task
    
    # Mock async_add_executor_job to run the function
    async def async_add_executor_job(func, *args):
        return func(*args)
    
    hass_mock.async_add_executor_job.side_effect = async_add_executor_job
    
    return hass_mock


@pytest.mark.asyncio
async def test_basic_task_execution(hass):
    """Test that tasks can be scheduled and executed."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    try:
        # Create a simple task
        async def test_task():
            return "success"
        
        # Schedule the task
        task = task_manager.schedule_task(test_task())
        assert task is not None
        
        # Wait for the task to complete
        result = await task
        assert result == "success"
        
        # Check stats
        stats = task_manager.get_stats()
        assert stats["completed_tasks"] == 1
        assert stats["failed_tasks"] == 0
        assert stats["active_tasks"] == 0
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_priority_tasks(hass):
    """Test that high priority tasks are executed with precedence."""
    task_manager = BackgroundTaskManager(hass, max_concurrent=1)
    await task_manager.async_start()
    
    try:
        results = []
        
        # Create tasks with delays
        async def normal_task():
            await asyncio.sleep(0.1)
            results.append("normal")
            return "normal"
        
        async def high_priority_task():
            results.append("high")
            return "high"
        
        # Schedule normal task (which will acquire the semaphore)
        normal_running = asyncio.Event()
        
        async def blocking_task():
            nonlocal normal_running
            normal_running.set()
            await asyncio.sleep(0.5)  # Block semaphore for a while
            results.append("blocking")
            return "blocking"
        
        task_manager.schedule_task(blocking_task())
        
        # Wait for the blocking task to start
        await normal_running.wait()
        
        # Now schedule a high priority task
        high_task = task_manager.schedule_task(high_priority_task(), priority="high")
        
        # Wait for high priority task to complete
        await high_task
        
        # Verify high priority executed first
        assert results[0] == "blocking"  # Was already running
        assert results[1] == "high"      # Next to run due to high priority
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_task_groups(hass):
    """Test that task groups work correctly."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    try:
        results = []
        
        # Create some tasks
        async def group_task(i):
            await asyncio.sleep(0.1)
            results.append(i)
            return i
        
        # Use a task group
        with task_manager.task_group() as group:
            tasks = []
            for i in range(5):
                task = group.schedule_task(group_task(i))
                tasks.append(task)
            
            # Wait for all tasks
            for task in asyncio.as_completed(tasks):
                await task
        
        # All tasks should have completed
        assert len(results) == 5
        assert set(results) == {0, 1, 2, 3, 4}
        
        # Test cancellation
        with task_manager.task_group() as group:
            long_task = group.schedule_task(asyncio.sleep(10))
            # Context manager will cancel the task when exiting
        
        # Task should be cancelled
        assert long_task.cancelled() or long_task.done()
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_executor_tasks(hass):
    """Test running tasks in the executor."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    try:
        # Create a CPU-bound function
        def cpu_task(n):
            return sum(i * i for i in range(n))
        
        # Schedule it
        task = task_manager.schedule_executor_job(cpu_task, 100)
        result = await task
        
        # Verify result
        assert result == sum(i * i for i in range(100))
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_error_handling(hass):
    """Test that errors in tasks are handled properly."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    try:
        # Create a task that raises an exception
        async def failing_task():
            raise ValueError("Test error")
        
        # Schedule it
        task = task_manager.schedule_task(failing_task())
        
        # It should fail but not crash the manager
        with pytest.raises(ValueError, match="Test error"):
            await task
        
        # Check stats
        stats = task_manager.get_stats()
        assert stats["completed_tasks"] == 0
        assert stats["failed_tasks"] == 1
        
        # We should still be able to schedule new tasks
        async def good_task():
            return "good"
        
        task = task_manager.schedule_task(good_task())
        result = await task
        assert result == "good"
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_task_cancellation(hass):
    """Test that tasks can be cancelled."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    try:
        # Schedule a long-running task
        async def long_task():
            try:
                await asyncio.sleep(10)
                return "completed"
            except asyncio.CancelledError:
                return "cancelled"
        
        task = task_manager.schedule_task(long_task())
        
        # Cancel it
        task.cancel()
        
        # Wait for it to complete
        with pytest.raises(asyncio.CancelledError):
            await task
        
        # Check stats
        stats = task_manager.get_stats()
        assert stats["cancelled_tasks"] == 1
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_shutdown_behavior(hass):
    """Test that shutdown properly cancels pending tasks."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    # Schedule some long-running tasks
    tasks = []
    for i in range(5):
        async def long_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                pass
        
        task = task_manager.schedule_task(long_task())
        tasks.append(task)
    
    # Shutdown should cancel all tasks
    await task_manager.async_stop()
    
    # All tasks should be cancelled
    for task in tasks:
        assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_periodic_tasks(hass):
    """Test periodic task scheduling."""
    task_manager = BackgroundTaskManager(hass)
    await task_manager.async_start()
    
    try:
        # Create a counter for our periodic task
        counter = 0
        
        async def periodic_task():
            nonlocal counter
            counter += 1
        
        # Schedule it to run frequently
        task = task_manager.schedule_periodic_task(periodic_task(), 0.1, "test_periodic")
        
        # Let it run a few times
        await asyncio.sleep(0.5)  # Should run about 5 times
        
        # Cancel the periodic task
        task.cancel()
        
        # The counter should have increased multiple times
        assert counter >= 3, f"Expected counter >= 3, got {counter}"
    finally:
        await task_manager.async_stop()


@pytest.mark.asyncio
async def test_resource_monitoring():
    """Test resource monitoring functionality (basic test only)."""
    # This is a minimal test since we can't easily mock CPU usage
    with patch("homeassistant.core.HomeAssistant") as hass_mock:
        # Setup the mock
        hass_mock.async_create_task.side_effect = lambda coro: asyncio.create_task(coro)
        
        task_manager = BackgroundTaskManager(hass_mock)
        
        # Mock psutil for testing
        with patch("importlib.import_module") as import_mock:
            # Start the task manager
            await task_manager.async_start()
            try:
                # Let resource monitor run
                await asyncio.sleep(0.1)
                
                # Basic test - just ensure it doesn't crash
                assert task_manager._active is True
            finally:
                await task_manager.async_stop()