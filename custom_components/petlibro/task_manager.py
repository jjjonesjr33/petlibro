"""PetLibro background task manager for performance optimization."""
import asyncio
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Set, Union

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manager for background tasks with concurrency control."""
    
    def __init__(self, hass: HomeAssistant, max_concurrent: int = 5):
        """Initialize the task manager.
        
        Args:
            hass: HomeAssistant instance
            max_concurrent: Maximum number of concurrent tasks
        """
        self.hass = hass
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._high_priority_semaphore = asyncio.Semaphore(2)  # Reserved for critical tasks
        self._tasks: Set[asyncio.Task] = set()
        self._task_stats = {
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "execution_times": [],  # Store recent execution times
        }
        self._cleanup_task = None
        self._active = False
        self._resource_monitor_task = None

    async def run_task(self, coro, priority="normal"):
        """Run a coroutine as a background task with concurrency control.
        
        Args:
            coro: The coroutine to execute
            priority: Task priority ("high" or "normal")
            
        Returns:
            The result of the coroutine execution
            
        Raises:
            asyncio.CancelledError: If the task is cancelled
            Exception: Any exception raised by the coroutine
        """
        # Determine which semaphore to use based on priority
        sem = self._high_priority_semaphore if priority == "high" else self._semaphore
        
        start_time = time.time()
        try:
            async with sem:
                if not self._active:
                    raise asyncio.CancelledError("Task manager is shutting down")
                result = await coro
                
                # Record statistics
                execution_time = time.time() - start_time
                self._task_stats["completed"] += 1
                self._task_stats["execution_times"].append(execution_time)
                if len(self._task_stats["execution_times"]) > 100:
                    self._task_stats["execution_times"].pop(0)  # Keep only recent times
                    
                return result
        except asyncio.CancelledError:
            self._task_stats["cancelled"] += 1
            raise
        except Exception as e:
            _LOGGER.error(f"Background task failed: {e}")
            self._task_stats["failed"] += 1
            raise

    def schedule_task(self, coro, priority="normal"):
        """Schedule a coroutine to run in the background.
        
        Args:
            coro: The coroutine to execute
            priority: Task priority ("high" or "normal")
            
        Returns:
            asyncio.Task or None: The scheduled task, or None if manager is shutting down
        """
        if not self._active:
            _LOGGER.warning("Attempted to schedule task while task manager is shutting down")
            return None
            
        task = self.hass.async_create_task(self.run_task(coro, priority))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def schedule_executor_job(self, func, *args, priority="normal"):
        """Schedule a CPU-bound function to run in the executor pool.
        
        Args:
            func: The function to execute
            *args: Arguments to pass to the function
            priority: Task priority ("high" or "normal")
            
        Returns:
            asyncio.Task or None: The scheduled task, or None if manager is shutting down
        """
        if not self._active:
            _LOGGER.warning("Attempted to schedule executor job while task manager is shutting down")
            return None
        
        async def _executor_job():
            return await self.hass.async_add_executor_job(func, *args)
        
        return self.schedule_task(_executor_job(), priority)

    @contextmanager
    def task_group(self):
        """Create a group of related tasks with context manager support.
        
        Example:
            ```python
            with task_manager.task_group() as group:
                group.schedule_task(task1())
                group.schedule_task(task2())
            # All tasks will be complete or cancelled when exiting the context
            ```
        
        Returns:
            _TaskGroup: A task group manager
        """
        group = _TaskGroup(self)
        try:
            yield group
        finally:
            group.cancel_all()

    def schedule_periodic_task(self, coro, interval, name=None):
        """Schedule a task to run periodically.
        
        Args:
            coro: The coroutine to execute periodically
            interval: Time between executions in seconds
            name: Optional name for the task
            
        Returns:
            asyncio.Task or None: The scheduled task, or None if manager is shutting down
        """
        if not self._active:
            _LOGGER.warning("Attempted to schedule periodic task while task manager is shutting down")
            return None
        
        task_name = name or str(uuid.uuid4())
        
        async def _periodic_runner():
            while self._active:
                try:
                    await self.run_task(coro, "normal")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    _LOGGER.error(f"Periodic task {task_name} failed: {e}")
                
                await asyncio.sleep(interval)
        
        task = self.hass.async_create_task(_periodic_runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _monitor_resources(self):
        """Monitor system resources and adjust concurrency limits."""
        try:
            import psutil
            have_psutil = True
        except ImportError:
            _LOGGER.info("psutil not available, resource monitoring will be limited")
            have_psutil = False

        while self._active:
            try:
                # Check number of active tasks
                active_tasks = len([t for t in self._tasks if not t.done()])
                
                if have_psutil:
                    # If CPU usage is high, reduce concurrency limit
                    if psutil.cpu_percent(interval=None) > 80 and self._semaphore._value < 3:
                        _LOGGER.warning("High CPU usage detected, reducing concurrency")
                        # Can't directly modify semaphore value, but can create a new one
                        # with a lower limit for future tasks
                        self._semaphore = asyncio.Semaphore(max(1, self._semaphore._value - 1))
                    
                    # If CPU usage is moderate and we're hitting limits, increase slightly
                    elif (
                        psutil.cpu_percent(interval=None) < 50
                        and active_tasks >= self._semaphore._value
                        and self._semaphore._value < 10
                    ):
                        _LOGGER.debug("Increasing task concurrency limit")
                        self._semaphore = asyncio.Semaphore(self._semaphore._value + 1)
                else:
                    # Simple heuristic without psutil
                    # If we have a lot of active tasks, consider reducing concurrency
                    if active_tasks > 10 and self._semaphore._value > 3:
                        _LOGGER.debug("Many active tasks, reducing concurrency")
                        self._semaphore = asyncio.Semaphore(max(2, self._semaphore._value - 1))
                    # If we're consistently hitting the limit, increase slightly
                    elif active_tasks >= self._semaphore._value and self._semaphore._value < 8:
                        _LOGGER.debug("Consistently hitting limits, increasing concurrency")
                        self._semaphore = asyncio.Semaphore(self._semaphore._value + 1)
                        
            except Exception as e:
                _LOGGER.error(f"Error in resource monitor: {e}")
                
            await asyncio.sleep(30)  # Check every 30 seconds

    async def async_start(self):
        """Start the task manager."""
        self._active = True
        self._cleanup_task = self.hass.async_create_task(self._cleanup_loop())
        
        # Start resource monitoring
        try:
            import psutil
            _LOGGER.debug("Starting resource monitoring with psutil")
        except ImportError:
            _LOGGER.debug("psutil not available, using basic resource monitoring")
            
        self._resource_monitor_task = self.schedule_periodic_task(
            self._monitor_resources(), 30, "resource_monitor"
        )
        
        _LOGGER.info("Background task manager started")

    async def async_stop(self):
        """Stop the task manager and cancel all pending tasks."""
        self._active = False
        
        # Cancel the cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        # Cancel all remaining tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            _, pending = await asyncio.wait(self._tasks, timeout=5)
            if pending:
                _LOGGER.warning(f"{len(pending)} tasks still pending after shutdown")
                
        _LOGGER.info("Background task manager stopped")

    async def _cleanup_loop(self):
        """Periodically clean up completed tasks from the task set."""
        while self._active:
            try:
                # Remove completed tasks that haven't been automatically removed
                for task in list(self._tasks):
                    if task.done():
                        self._tasks.discard(task)
                
                # Trim execution times list if it gets too long
                if len(self._task_stats["execution_times"]) > 100:
                    self._task_stats["execution_times"] = self._task_stats["execution_times"][-100:]
                    
            except Exception as e:
                _LOGGER.error(f"Error in cleanup loop: {e}")
                
            await asyncio.sleep(60)  # Run cleanup every minute

    def get_stats(self):
        """Return statistics about task execution.
        
        Returns:
            dict: Task statistics including counts, execution times, and concurrency limits
        """
        active_tasks = len([t for t in self._tasks if not t.done()])
        
        stats = {
            "active_tasks": active_tasks,
            "total_tasks": len(self._tasks),
            "completed_tasks": self._task_stats["completed"],
            "failed_tasks": self._task_stats["failed"],
            "cancelled_tasks": self._task_stats["cancelled"],
            "concurrency_limit": self._semaphore._value,
            "high_priority_limit": self._high_priority_semaphore._value,
        }
        
        # Add average execution time if we have data
        if self._task_stats["execution_times"]:
            avg_time = sum(self._task_stats["execution_times"]) / len(self._task_stats["execution_times"])
            stats["avg_execution_time"] = avg_time
        
        return stats


class _TaskGroup:
    """A group of related tasks that can be managed together."""
    
    def __init__(self, manager):
        """Initialize with reference to the task manager.
        
        Args:
            manager: BackgroundTaskManager instance
        """
        self.manager = manager
        self.tasks = set()
    
    def schedule_task(self, coro, priority="normal"):
        """Schedule a task as part of this group.
        
        Args:
            coro: The coroutine to execute
            priority: Task priority ("high" or "normal")
            
        Returns:
            asyncio.Task or None: The scheduled task
        """
        task = self.manager.schedule_task(coro, priority)
        if task:
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
        return task
    
    def cancel_all(self):
        """Cancel all tasks in this group."""
        for task in list(self.tasks):
            if not task.done():
                task.cancel()
        self.tasks.clear()