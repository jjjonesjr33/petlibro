"""PetLibro command queue system for reliable device control during API outages."""
import asyncio
import gzip
import json
import logging
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from homeassistant.core import HomeAssistant, callback
from .const import DEFAULT_MAX_BACKOFF_TIME

_LOGGER = logging.getLogger(__name__)


class CommandEntry:
    """A command in the queue."""

    def __init__(
        self,
        device_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None,
        priority: int = 0,
    ):
        """Initialize a command entry.
        
        Args:
            device_id: The ID of the device the command is for
            command: The command name (corresponds to API method name)
            params: Optional parameters for the command
            callback: Optional callback function to call when command completes
            priority: Command priority (higher number = higher priority)
        """
        self.id = str(uuid.uuid4())
        self.device_id = device_id
        self.command = command
        self.params = params or {}
        self.callback = callback
        self.created_at = time.time()
        self.executed_at = None
        self.retries = 0
        self.max_retries = 5
        self.retry_delay_base = 2  # Base for exponential backoff
        self.retry_delay_max = DEFAULT_MAX_BACKOFF_TIME  # Maximum retry delay in seconds
        self.status = "pending"  # pending, executing, completed, failed
        self.result = None
        self.error = None
        self.priority = priority  # Higher number = higher priority
        self.next_retry_time = None  # When to next retry this command

    def to_json(self) -> Dict[str, Any]:
        """Convert the command entry to a JSON-serializable dict."""
        # Don't include callback in the serialized data
        return {
            "id": self.id,
            "device_id": self.device_id,
            "command": self.command,
            "params": self.params,
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "next_retry_time": self.next_retry_time,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "CommandEntry":
        """Create a command entry from JSON data."""
        entry = cls(
            device_id=data["device_id"],
            command=data["command"],
            params=data.get("params", {}),
            priority=data.get("priority", 0),
        )
        # Restore other properties
        entry.id = data["id"]
        entry.created_at = data["created_at"]
        entry.executed_at = data.get("executed_at")
        entry.retries = data.get("retries", 0)
        entry.max_retries = data.get("max_retries", 5)
        entry.status = data.get("status", "pending")
        entry.result = data.get("result")
        entry.error = data.get("error")
        entry.next_retry_time = data.get("next_retry_time")
        return entry

    def set_retry_time(self) -> None:
        """Calculate the next retry time using exponential backoff with jitter."""
        import random
        # Calculate backoff time using exponential backoff with a bit of randomness
        delay = min(
            self.retry_delay_base ** self.retries + random.uniform(0, 1),
            self.retry_delay_max
        )
        self.next_retry_time = time.time() + delay
        _LOGGER.debug(
            "Command %s scheduled for retry in %.1f seconds (retry %d/%d)",
            self.id,
            delay,
            self.retries,
            self.max_retries
        )


class CommandQueue:
    """Queue for PetLibro device commands."""

    def __init__(self, hass: HomeAssistant, hub):
        """Initialize the command queue.
        
        Args:
            hass: HomeAssistant instance
            hub: The PetLibro hub instance
        """
        self.hass = hass
        self.hub = hub
        self.queue_file = os.path.join(
            hass.config.path(), f"petlibro_cmdqueue_{hub.config_entry_id}.json.gz"
        )
        self.queue: List[CommandEntry] = []
        self.processing = False
        self._lock = asyncio.Lock()
        self._command_callbacks: Dict[str, Callable] = {}  # Store callbacks by command ID
        self.last_save = 0
        self.save_interval = 60  # Save at most once per minute
        self.dirty = False
        self._task = None  # Background processing task

        # Schedule initial queue load
        self.hass.async_create_task(self._load_queue())

    async def _load_queue(self) -> None:
        """Load queue from persistent storage."""
        async with self._lock:
            def _load_file() -> List[Dict[str, Any]]:
                """Load queue file from disk (runs in executor)."""
                if not os.path.exists(self.queue_file):
                    return []

                try:
                    with gzip.open(self.queue_file, "rt") as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError, gzip.BadGzipFile) as err:
                    _LOGGER.error("Failed to load command queue from %s: %s", self.queue_file, err)
                    
                    # Try to recover from uncompressed file if exists
                    uncompressed_file = self.queue_file.replace(".gz", "")
                    if os.path.exists(uncompressed_file):
                        try:
                            _LOGGER.info("Attempting to load from uncompressed backup %s", uncompressed_file)
                            with open(uncompressed_file, "r") as f:
                                return json.load(f)
                        except (json.JSONDecodeError, IOError) as err2:
                            _LOGGER.error("Failed to load uncompressed command queue: %s", err2)
                
                return []

            # Load file in executor to avoid blocking
            queue_data = await self.hass.async_add_executor_job(_load_file)
            
            # Convert JSON data back to CommandEntry objects
            self.queue = [CommandEntry.from_json(item) for item in queue_data]
            
            # Reset status for any commands that were executing
            for cmd in self.queue:
                if cmd.status == "executing":
                    cmd.status = "pending"
                    
            _LOGGER.debug("Loaded command queue with %d commands", len(self.queue))

    async def _save_queue(self) -> None:
        """Save queue to persistent storage."""
        if not self.dirty:
            return

        async with self._lock:
            def _save_file(queue_data: List[Dict[str, Any]]) -> None:
                """Save queue file to disk (runs in executor)."""
                try:
                    # Save to temp file first
                    temp_file = f"{self.queue_file}.tmp"
                    
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)

                    with gzip.open(temp_file, "wt") as f:
                        json.dump(queue_data, f)
                    
                    # Also save uncompressed backup
                    uncompressed_file = self.queue_file.replace(".gz", "")
                    with open(uncompressed_file, "w") as f:
                        json.dump(queue_data, f)
                    
                    # Replace the actual file (atomic operation)
                    os.replace(temp_file, self.queue_file)
                    
                    _LOGGER.debug("Command queue saved to %s", self.queue_file)
                except (IOError, gzip.BadGzipFile) as err:
                    _LOGGER.error("Failed to save command queue to %s: %s", self.queue_file, err)

            # Convert CommandEntry objects to serializable dicts
            queue_data = [cmd.to_json() for cmd in self.queue]
            
            # Save file in executor to avoid blocking
            await self.hass.async_add_executor_job(_save_file, queue_data)
            self.last_save = time.time()
            self.dirty = False

    async def async_add_command(
        self,
        device_id: str,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None,
        priority: int = 0,
    ) -> str:
        """Add a command to the queue.
        
        Args:
            device_id: The ID of the device the command is for
            command: The command name (corresponds to API method name)
            params: Optional parameters for the command
            callback: Optional callback function to call when command completes
            priority: Command priority (higher number = higher priority)
            
        Returns:
            The ID of the queued command
        """
        async with self._lock:
            cmd = CommandEntry(
                device_id=device_id,
                command=command,
                params=params,
                callback=callback,
                priority=priority,
            )
            
            # Store callback separately (won't be serialized)
            if callback is not None:
                self._command_callbacks[cmd.id] = callback
                
            self.queue.append(cmd)
            self.dirty = True
            
            # Schedule a save if it's been a while
            if time.time() - self.last_save >= self.save_interval:
                self.hass.async_create_task(self._save_queue())
                
            # Start processing if not already running
            if not self.processing and self._task is None:
                self._task = self.hass.async_create_task(self.async_process_queue())
                
            _LOGGER.debug(
                "Command queued: %s, device: %s, priority: %d, id: %s",
                command,
                device_id,
                priority,
                cmd.id
            )
            
            return cmd.id

    async def _update_command_status(self, cmd: CommandEntry, status: str, reason: Optional[str] = None) -> None:
        """Update command status and fire event.
        
        Args:
            cmd: The command to update
            status: The new status
            reason: Optional reason for the status change
        """
        old_status = cmd.status
        cmd.status = status
        
        if reason:
            cmd.error = reason
            
        self.dirty = True
        
        # Get device info for the notification
        device = await self.hub.get_device(cmd.device_id)
        device_name = getattr(device, "name", cmd.device_id) if device else cmd.device_id
        
        # Fire event for the notification manager
        self.hass.bus.async_fire(
            "petlibro_command_status",
            {
                "command": cmd.command,
                "device_id": cmd.device_id,
                "device_name": device_name,
                "status": status,
                "was_queued": old_status == "pending",
                "reason": reason,
                "retries": cmd.retries
            }
        )

    async def async_process_queue(self) -> None:
        """Process the command queue."""
        if self.processing:
            return
        
        self.processing = True
        
        try:
            while True:
                # Get pending commands
                async with self._lock:
                    # Sort by priority (highest first) then by creation time
                    pending_commands = sorted(
                        [c for c in self.queue if c.status == "pending"],
                        key=lambda x: (-x.priority, x.created_at)
                    )
                    
                    # Filter for commands that are ready to be executed (respect retry delay)
                    current_time = time.time()
                    ready_commands = [
                        c for c in pending_commands 
                        if c.next_retry_time is None or current_time >= c.next_retry_time
                    ]
                    
                    if not ready_commands:
                        # If we have pending commands but none are ready, sleep until next retry
                        if pending_commands:
                            next_retry = min([
                                c.next_retry_time for c in pending_commands 
                                if c.next_retry_time is not None
                            ], default=None)
                            
                            if next_retry:
                                wait_time = max(0.1, next_retry - current_time)
                                _LOGGER.debug("Waiting %.1f seconds for next retry", wait_time)
                                await asyncio.sleep(wait_time)
                                continue
                        
                        # No commands to process
                        break
                        
                    # Get the highest priority command that's ready
                    cmd = ready_commands[0]
                    
                    # Check API connection state
                    if self.hub.api.session.connection_state == "offline":
                        _LOGGER.debug("API is offline, pausing queue processing")
                        await asyncio.sleep(10)  # Check again after a delay
                        continue
                        
                    # Mark as executing
                    await self._update_command_status(cmd, "executing")
                
                # Execute command outside the lock
                await self._execute_command(cmd)
                
                # Save queue after command execution
                await self._save_queue()
                
                # Small pause between processing commands to avoid overwhelming the API
                await asyncio.sleep(0.5)
            
        except asyncio.CancelledError:
            _LOGGER.debug("Command queue processing cancelled")
            
        except Exception as e:
            _LOGGER.exception("Error processing command queue: %s", e)
            
        finally:
            self.processing = False
            self._task = None
    
    async def _execute_command(self, cmd: CommandEntry) -> None:
        """Execute a command and update its status.
        
        Args:
            cmd: The command to execute
        """
        _LOGGER.debug(
            "Executing command: %s for device %s (retry %d/%d)",
            cmd.command,
            cmd.device_id,
            cmd.retries,
            cmd.max_retries
        )
        
        try:
            # Get the device
            device = await self.hub.get_device(cmd.device_id)
            if not device:
                await self._update_command_status(cmd, "failed", f"Device {cmd.device_id} not found")
                _LOGGER.error("Device %s not found for command %s", cmd.device_id, cmd.id)
                self._call_command_callback(cmd)
                return
            
            # Find the command method on the device or API
            method = getattr(device, f"set_{cmd.command}", None)
            if method is None:
                # Try the API directly if not found on device
                method = getattr(self.hub.api, f"set_{cmd.command}", None)
                
            if method is None:
                await self._update_command_status(cmd, "failed", f"Command '{cmd.command}' not supported by device")
                _LOGGER.error("Command '%s' not supported for device %s", cmd.command, cmd.device_id)
                self._call_command_callback(cmd)
                return
            
            # Call the method with parameters
            try:
                if cmd.params:
                    result = await method(**cmd.params)
                else:
                    result = await method()
                
                # Command succeeded
                cmd.executed_at = time.time()
                cmd.result = result
                await self._update_command_status(cmd, "completed")
                
                _LOGGER.debug(
                    "Command %s executed successfully for device %s",
                    cmd.command,
                    cmd.device_id
                )
                
            except Exception as e:
                # Command failed
                cmd.retries += 1
                if cmd.retries >= cmd.max_retries:
                    await self._update_command_status(cmd, "failed", str(e))
                    _LOGGER.error(
                        "Command %s failed after %d retries: %s",
                        cmd.command,
                        cmd.retries,
                        e
                    )
                else:
                    # Put back in pending state for retry
                    await self._update_command_status(cmd, "pending", str(e))
                    cmd.set_retry_time()
                    _LOGGER.warning(
                        "Command %s failed, will retry (%d/%d): %s",
                        cmd.command,
                        cmd.retries,
                        cmd.max_retries,
                        e
                    )
                
            # Call command callback
            self._call_command_callback(cmd)
                
        except Exception as e:
            _LOGGER.exception("Unexpected error executing command %s: %s", cmd.id, e)
            await self._update_command_status(cmd, "failed", f"Unexpected error: {str(e)}")
            self._call_command_callback(cmd)

    def _call_command_callback(self, cmd: CommandEntry) -> None:
        """Call the command callback if one exists.
        
        Args:
            cmd: The command whose callback to call
        """
        callback = self._command_callbacks.get(cmd.id)
        if callback is not None:
            try:
                callback(cmd)
            except Exception as e:
                _LOGGER.error("Error calling command callback: %s", e)
            
            # If command is completed or failed, remove the callback reference
            if cmd.status in ("completed", "failed"):
                self._command_callbacks.pop(cmd.id, None)

    def get_command_status(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a command.
        
        Args:
            command_id: The ID of the command
            
        Returns:
            Command status information or None if not found
        """
        for cmd in self.queue:
            if cmd.id == command_id:
                return {
                    "id": cmd.id,
                    "device_id": cmd.device_id,
                    "command": cmd.command,
                    "status": cmd.status,
                    "created_at": cmd.created_at,
                    "executed_at": cmd.executed_at,
                    "retries": cmd.retries,
                    "error": cmd.error,
                    "priority": cmd.priority,
                }
        return None

    async def async_clear_queue(self) -> int:
        """Clear the entire queue.
        
        Returns:
            Number of commands cleared
        """
        async with self._lock:
            count = len(self.queue)
            self.queue = []
            self._command_callbacks = {}
            self.dirty = True
            await self._save_queue()
            return count

    async def async_set_command_priority(
        self, command_id: str, priority: int
    ) -> bool:
        """Set the priority of a command.
        
        Args:
            command_id: The ID of the command
            priority: The new priority value
            
        Returns:
            True if command was found and updated, False otherwise
        """
        async with self._lock:
            for cmd in self.queue:
                if cmd.id == command_id and cmd.status == "pending":
                    cmd.priority = priority
                    self.dirty = True
                    await self._save_queue()
                    return True
            return False

    async def async_cancel_command(self, command_id: str) -> bool:
        """Cancel a pending command.
        
        Args:
            command_id: The ID of the command
            
        Returns:
            True if command was found and cancelled, False otherwise
        """
        async with self._lock:
            for i, cmd in enumerate(self.queue):
                if cmd.id == command_id:
                    if cmd.status == "pending":
                        # Remove callback if exists
                        self._command_callbacks.pop(cmd.id, None)
                        # Remove command from queue
                        self.queue.pop(i)
                        self.dirty = True
                        await self._save_queue()
                        return True
                    # Command is already executing, completed, or failed
                    return False
            return False

    async def async_start(self) -> None:
        """Start the command queue background processing."""
        if not self.processing and self._task is None:
            self._task = self.hass.async_create_task(self.async_process_queue())
            _LOGGER.debug("Command queue processing started")

    async def async_stop(self) -> None:
        """Stop the command queue background processing."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            self.processing = False
            _LOGGER.debug("Command queue processing stopped")

    def _background_save_loop(self) -> None:
        """Background task that periodically saves the queue."""
        async def _save_loop():
            while True:
                # Check if save is needed
                if self.dirty and (time.time() - self.last_save) >= self.save_interval:
                    await self._save_queue()
                
                # Sleep for a while
                await asyncio.sleep(60)  # Check every minute
        
        self.hass.async_create_task(_save_loop())

    def get_queue_stats(self) -> Dict[str, int]:
        """Get statistics about the command queue.
        
        Returns:
            Dictionary with queue statistics
        """
        pending = 0
        executing = 0
        completed = 0
        failed = 0
        
        for cmd in self.queue:
            if cmd.status == "pending":
                pending += 1
            elif cmd.status == "executing":
                executing += 1
            elif cmd.status == "completed":
                completed += 1
            elif cmd.status == "failed":
                failed += 1
                
        return {
            "pending": pending,
            "executing": executing,
            "completed": completed,
            "failed": failed,
            "total": len(self.queue),
        }

    def start_background_save(self) -> None:
        """Start the background save loop."""
        self._background_save_loop()