"""PetLibro adaptive polling coordinator for resource optimization."""
import asyncio
import copy
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class AdaptivePollingCoordinator(DataUpdateCoordinator):
    """Coordinator with adaptive polling intervals."""
    
    def __init__(
        self, 
        hass: HomeAssistant, 
        logger: logging.Logger,
        name: str,
        update_method: Callable,
        min_update_interval: timedelta = timedelta(seconds=30),
        max_update_interval: timedelta = timedelta(minutes=10),
        task_manager = None,
    ):
        """Initialize with adaptive polling.
        
        Args:
            hass: HomeAssistant instance
            logger: Logger instance 
            name: Coordinator name
            update_method: Method to call for updates
            min_update_interval: Minimum time between updates
            max_update_interval: Maximum time between updates
            task_manager: Optional task manager for background processing
        """
        self.min_update_interval = min_update_interval
        self.max_update_interval = max_update_interval
        self.current_interval = max_update_interval
        self.last_activity_time = time.time()
        self.task_manager = task_manager
        self.activity_counter = 0
        self.usage_patterns = {
            # hour -> frequency multiplier (1.0 = normal, <1 = more frequent, >1 = less frequent)
            # Default to normal frequency for all hours
            hour: 1.0 for hour in range(24)
        }
        self.api_performance = {
            "success_rate": 1.0,  # Assume good performance initially
            "response_times": [],
        }
        
        # Last result tracking
        self._last_changes = {}
        self._last_result = None
        
        super().__init__(
            hass,
            logger,
            name=name,
            update_method=self._adaptive_update,
            update_interval=self.current_interval,
        )
    
    def register_activity(self, device_id=None, action=None):
        """Register device activity to temporarily increase polling frequency.
        
        Args:
            device_id: Optional device identifier
            action: Optional action name that triggered activity
        """
        self.last_activity_time = time.time()
        self.activity_counter += 1
        
        # Update the usage pattern for current hour
        current_hour = datetime.now().hour
        # Gradually lower the multiplier for active hours (more frequent polling)
        self.usage_patterns[current_hour] = max(0.5, self.usage_patterns[current_hour] * 0.95)
        
        # Immediately increase polling frequency if we're at a low frequency
        if self.current_interval > self.min_update_interval:
            self._adjust_polling_frequency()
            self.update_interval = self.current_interval
            self.logger.debug(f"Increased polling frequency due to activity: {self.current_interval}")
            
        # Log activity for debugging
        if device_id and action:
            self.logger.debug(f"Registered activity for device {device_id}: {action}")
        elif device_id:
            self.logger.debug(f"Registered activity for device {device_id}")
        elif action:
            self.logger.debug(f"Registered activity: {action}")
        else:
            self.logger.debug("Registered generic activity")

    def _learn_usage_patterns(self):
        """Analyze activity patterns to optimize polling schedule."""
        # Calculate activity levels by hour based on recorded activities
        hour_now = datetime.now().hour
        
        # Slowly drift all hours toward normal frequency
        for hour in range(24):
            if hour == hour_now:
                continue  # Current hour is handled by register_activity
                
            # If not current hour, gradually return to normal (1.0)
            if self.usage_patterns[hour] < 1.0:
                self.usage_patterns[hour] = min(1.0, self.usage_patterns[hour] * 1.01)
            elif self.usage_patterns[hour] > 1.0:
                self.usage_patterns[hour] = max(1.0, self.usage_patterns[hour] * 0.99)
                
        # Log current patterns periodically (every 24 hours)
        if self.activity_counter % 1440 == 0:  # Assuming 1-minute polling on average (24 hours = 1440 minutes)
            sorted_hours = sorted(
                [(hour, factor) for hour, factor in self.usage_patterns.items()], 
                key=lambda x: x[1]
            )
            most_active = sorted_hours[:3]  # Top 3 most active hours (lowest multiplier)
            least_active = sorted_hours[-3:]  # Top 3 least active hours (highest multiplier)
            self.logger.info(
                f"Activity patterns - Most active hours: {most_active}, Least active: {least_active}"
            )

    def record_api_result(self, success: bool, response_time: float):
        """Record API performance metrics.
        
        Args:
            success: Whether the API call was successful
            response_time: Time taken for the API call in seconds
        """
        # Keep recent response times (last 50)
        self.api_performance["response_times"].append(response_time)
        if len(self.api_performance["response_times"]) > 50:
            self.api_performance["response_times"] = self.api_performance["response_times"][-50:]
        
        # Update success rate with exponential decay (more weight to recent results)
        if success:
            self.api_performance["success_rate"] = 0.9 * self.api_performance["success_rate"] + 0.1
        else:
            self.api_performance["success_rate"] = 0.9 * self.api_performance["success_rate"]
        
        # Adjust polling based on API performance
        self._adjust_for_api_performance()
        
        # Log performance metrics periodically
        if len(self.api_performance["response_times"]) % 10 == 0:
            avg_time = sum(self.api_performance["response_times"]) / len(self.api_performance["response_times"])
            self.logger.debug(
                f"API performance metrics - Success rate: {self.api_performance['success_rate']:.2f}, "
                f"Avg response time: {avg_time:.2f}s"
            )

    def _adjust_for_api_performance(self):
        """Adjust polling based on API performance."""
        # If performance is poor, adjust polling frequency
        performance_factor = self._get_api_performance_factor()
        
        if performance_factor > 1.2:
            # API is struggling, reduce polling frequency
            self.logger.debug(f"Reducing polling frequency due to API performance issues (factor: {performance_factor})")
            self._adjust_polling_frequency()
            self.update_interval = self.current_interval
        elif performance_factor < 0.8:
            # API is performing well, can increase frequency slightly if appropriate
            self.logger.debug(f"API performing well, may adjust polling frequency (factor: {performance_factor})")
            self._adjust_polling_frequency()
            self.update_interval = self.current_interval

    def _adjust_polling_frequency(self):
        """Adjust polling frequency based on multiple factors."""
        # Start from base interval
        target_interval = self.max_update_interval.total_seconds()
        
        # Factor 1: Recent activity
        time_since_activity = time.time() - self.last_activity_time
        if time_since_activity < 300:  # 5 minutes
            # Scale linearly from min to max over 5 minutes of inactivity
            activity_factor = time_since_activity / 300
            target_interval *= activity_factor
        
        # Factor 2: Time of day pattern
        current_hour = datetime.now().hour
        time_of_day_factor = self.usage_patterns[current_hour]
        target_interval *= time_of_day_factor
        
        # Factor 3: API performance
        performance_factor = self._get_api_performance_factor()
        target_interval *= performance_factor
        
        # Apply constraints
        target_interval = max(
            self.min_update_interval.total_seconds(),
            min(self.max_update_interval.total_seconds(), target_interval)
        )
        
        # Convert back to timedelta
        new_interval = timedelta(seconds=target_interval)
        
        # Only log if there's a significant change
        if abs((new_interval - self.current_interval).total_seconds()) > 5:
            self.logger.debug(
                f"Adjusted polling frequency from {self.current_interval} to {new_interval} "
                f"(activity: {time_since_activity:.1f}s, hour: {current_hour}, "
                f"hourly factor: {time_of_day_factor:.2f}, performance: {performance_factor:.2f})"
            )
            
        self.current_interval = new_interval

    def _get_api_performance_factor(self):
        """Calculate a factor for API performance (higher = slower polling).
        
        Returns:
            float: Performance factor (>1 = reduce polling, <1 = increase polling)
        """
        # If API is performing poorly, reduce polling frequency
        success_rate = self.api_performance["success_rate"]
        
        if success_rate < 0.5:  # Less than 50% success
            return 2.0  # Poll half as often
        elif success_rate < 0.8:  # 50-80% success
            return 1.5  # Poll 2/3 as often
        elif success_rate > 0.95:  # Very reliable
            return 0.9  # Poll slightly more often
        
        # Default: neutral factor
        return 1.0
        
    def _detect_important_changes(self, result):
        """Detect if important changes have occurred in the data.
        
        Args:
            result: The latest data from the update
            
        Returns:
            bool: True if important changes were detected
        """
        if self._last_result is None:
            self._last_result = copy.deepcopy(result)
            return True  # First result is always important
        
        important_change = False
        
        # Check each device
        for device_id, device_data in result.items():
            if device_id not in self._last_result:
                important_change = True
                continue
                
            # Check for specific important changes
            old_data = self._last_result[device_id]
            
            # Define important attributes to check
            important_attrs = [
                "online",
                "batteryState",
                "enableFeedingPlan",
                "childLockSwitch",
                "feeding_plan_state", 
                # Add other critical attributes here
            ]
            
            for attr in important_attrs:
                if attr in device_data and attr in old_data:
                    if device_data[attr] != old_data[attr]:
                        self._last_changes[attr] = time.time()
                        important_change = True
        
        # Update last result
        self._last_result = copy.deepcopy(result)
        return important_change

    async def _adaptive_update(self):
        """Update method that adapts polling behavior based on results.
        
        Returns:
            Any: The result of the update method
            
        Raises:
            Exception: Any error from the update method
        """
        start_time = time.time()
        success = True
        
        try:
            # Use task manager if available, otherwise call directly
            if self.task_manager:
                result = await self.task_manager.run_task(self.update_method())
            else:
                result = await self.update_method()
                
            # Check for important changes
            important_changes = self._detect_important_changes(result)
            if important_changes:
                # If important changes detected, register activity to increase polling
                self.register_activity(action="important_changes_detected")
                
            # Learn from patterns periodically
            self._learn_usage_patterns()
            
            return result
        except Exception as e:
            success = False
            self.logger.error(f"Error in update: {e}")
            raise
        finally:
            # Record API performance
            execution_time = time.time() - start_time
            self.record_api_result(success, execution_time)
            
            # Adjust polling frequency for next update
            self._adjust_polling_frequency()
            if self.update_interval != self.current_interval:
                self.update_interval = self.current_interval

    async def async_adjust_update_interval(self, interval: timedelta):
        """Temporarily adjust the update interval.
        
        Args:
            interval: The new interval to use temporarily
        """
        self.logger.debug(f"Manually adjusting update interval to {interval}")
        self.update_interval = interval
        
        # Schedule returning to adaptive interval after a fixed time
        async def _restore_adaptive():
            await asyncio.sleep(interval.total_seconds() * 2)  # Wait for double the requested interval
            self._adjust_polling_frequency()  # Return to normal adaptive behavior
            self.update_interval = self.current_interval
            self.logger.debug(f"Restored adaptive polling with interval {self.current_interval}")
        
        if self.task_manager:
            self.task_manager.schedule_task(_restore_adaptive())
        else:
            asyncio.create_task(_restore_adaptive())
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the adaptive polling.
        
        Returns:
            Dict: Dictionary containing statistics about polling behavior
        """
        current_hour = datetime.now().hour
        
        # Calculate average response time
        avg_response_time = 0
        if self.api_performance["response_times"]:
            avg_response_time = sum(self.api_performance["response_times"]) / len(self.api_performance["response_times"])
            
        # Sort hours by activity level (most active first)
        active_hours = sorted(
            [(hour, factor) for hour, factor in self.usage_patterns.items()], 
            key=lambda x: x[1]
        )
        
        return {
            "current_interval": self.current_interval.total_seconds(),
            "min_interval": self.min_update_interval.total_seconds(),
            "max_interval": self.max_update_interval.total_seconds(),
            "time_since_activity": time.time() - self.last_activity_time,
            "activity_counter": self.activity_counter,
            "current_hour_factor": self.usage_patterns[current_hour],
            "api_success_rate": self.api_performance["success_rate"],
            "avg_response_time": avg_response_time,
            "most_active_hours": active_hours[:3],  # Top 3 most active hours
            "least_active_hours": active_hours[-3:],  # Top 3 least active hours
        }