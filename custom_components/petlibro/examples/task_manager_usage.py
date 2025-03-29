"""Example usage of the BackgroundTaskManager."""
import asyncio
import logging
import time
from homeassistant.core import HomeAssistant

from ..task_manager import BackgroundTaskManager

_LOGGER = logging.getLogger(__name__)


async def example_usage(hass: HomeAssistant):
    """Demonstrate how to use the BackgroundTaskManager."""
    
    # Initialize the task manager with a max concurrency limit of 5
    task_manager = BackgroundTaskManager(hass, max_concurrent=5)
    
    # Start the task manager (activates background monitoring)
    await task_manager.async_start()
    
    try:
        # Example 1: Basic task scheduling
        # --------------------------------
        _LOGGER.info("Scheduling a basic task")
        
        async def sample_task():
            """A simple asynchronous task."""
            _LOGGER.info("Starting sample task")
            await asyncio.sleep(2)  # Simulate work
            _LOGGER.info("Sample task completed")
            return "Task result"
        
        # Schedule a task and get its result
        task = task_manager.schedule_task(sample_task())
        result = await task
        _LOGGER.info(f"Task completed with result: {result}")
        
        # Example 2: High priority tasks
        # -----------------------------
        _LOGGER.info("Scheduling a high priority task")
        
        async def critical_task():
            """A high priority task that should execute with precedence."""
            _LOGGER.info("Starting critical task")
            await asyncio.sleep(1)
            _LOGGER.info("Critical task completed")
            return "Critical completed"
        
        # Schedule as high priority
        critical_result = await task_manager.run_task(critical_task(), priority="high")
        _LOGGER.info(f"Critical task result: {critical_result}")
        
        # Example 3: Task groups for related operations
        # --------------------------------------------
        _LOGGER.info("Using task groups for related operations")
        
        async def device_task(device_id):
            """Simulate a device-specific task."""
            _LOGGER.info(f"Processing device {device_id}")
            await asyncio.sleep(device_id * 0.5)  # Simulate varying work
            return f"Device {device_id} processed"
        
        # Use a task group to handle multiple related tasks
        with task_manager.task_group() as group:
            # Schedule multiple related tasks
            tasks = []
            for i in range(5):
                task = group.schedule_task(device_task(i))
                tasks.append(task)
                
            # Get results as they complete
            for task in asyncio.as_completed(tasks):
                result = await task
                _LOGGER.info(f"Task completed: {result}")
        
        # When exiting the context manager, any incomplete tasks are cancelled
        
        # Example 4: CPU-bound tasks in executor
        # ------------------------------------
        _LOGGER.info("Scheduling CPU-bound task in executor")
        
        def cpu_intensive_task(iterations):
            """A CPU-intensive task that runs in the executor pool."""
            _LOGGER.info(f"Starting CPU-intensive task with {iterations} iterations")
            result = 0
            start = time.time()
            for i in range(iterations):
                result += i * i
            elapsed = time.time() - start
            _LOGGER.info(f"CPU task completed in {elapsed:.2f}s")
            return result
        
        # Schedule in the executor pool
        cpu_result = await task_manager.schedule_executor_job(cpu_intensive_task, 1000000)
        _LOGGER.info(f"CPU task result: {cpu_result}")
        
        # Example 5: Periodic tasks
        # -----------------------
        _LOGGER.info("Setting up a periodic task")
        
        async def periodic_operation():
            """A task that should run periodically."""
            _LOGGER.info("Periodic task running")
            await asyncio.sleep(0.5)  # Simulate some work
            return "Periodic complete"
        
        # Schedule to run every 10 seconds
        periodic_task = task_manager.schedule_periodic_task(
            periodic_operation(), 
            interval=10, 
            name="example_periodic"
        )
        
        # Let it run a couple of times
        await asyncio.sleep(25)
        
        # Example 6: Get statistics
        # -----------------------
        stats = task_manager.get_stats()
        _LOGGER.info(f"Task manager statistics: {stats}")
        
        # Clean up the periodic task
        periodic_task.cancel()
        
    finally:
        # Always stop the task manager when done
        await task_manager.async_stop()
        _LOGGER.info("Task manager stopped")


async def example_integration_with_hub(hub):
    """Demonstrate how to use BackgroundTaskManager with the PetLibro hub."""
    
    # The hub already has a task_manager instance initialized
    task_manager = hub.task_manager
    
    # Example: Schedule a device refresh as a background task
    for device in hub.devices:
        task_manager.schedule_task(device.refresh())
    
    # Example: Run a critical command with high priority
    if hub.devices:
        device = hub.devices[0]
        await device.execute_critical_command("some_critical_command", param1="value1")
    
    # Example: Schedule periodic background maintenance
    async def clean_old_data():
        """Periodically clean up old data."""
        # Example implementation
        _LOGGER.info("Cleaning up old data")
        
    task_manager.schedule_periodic_task(clean_old_data(), 3600, "data_cleanup")
    
    # Get task manager stats
    stats = hub.get_task_manager_stats()
    _LOGGER.info(f"Task manager statistics: {stats}")