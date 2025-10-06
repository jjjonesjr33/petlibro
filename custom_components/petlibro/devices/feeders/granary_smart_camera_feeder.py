import aiohttp

from typing import cast
from logging import getLogger
from ...exceptions import PetLibroAPIError
from ..device import Device
from datetime import datetime
from homeassistant.util import dt as dt_util

_LOGGER = getLogger(__name__)

class GranarySmartCameraFeeder(Device):  # Inherit directly from Device
    def __init__(self, *args, **kwargs):
        """Initialize the feeder with default values."""
        super().__init__(*args, **kwargs)
        self._manual_feed_quantity = None  # Default to None initially

    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            await super().refresh()  # Call the refresh method from Device
    
            # Fetch specific data for this device
            grain_status = await self.api.device_grain_status(self.serial)
            real_info = await self.api.device_real_info(self.serial)
            attribute_settings = await self.api.device_attribute_settings(self.serial)
            get_upgrade = await self.api.get_device_upgrade(self.serial)
            get_feeding_plan_today = await self.api.device_feeding_plan_today_new(self.serial)
    
            # Update internal data with fetched API data
            self.update_data({
                "grainStatus": grain_status or {},
                "realInfo": real_info or {},
                "getAttributeSetting": attribute_settings or {},
                "getUpgrade": get_upgrade or {},
                "getfeedingplantoday": get_feeding_plan_today or {}
            })
        except PetLibroAPIError as err:
            _LOGGER.error(f"Error refreshing data for GranarySmartCameraFeeder: {err}")

    @property
    def available(self) -> bool:
        _LOGGER.debug(f"Device {self.device.name} availability: {self.device.online}")
        return self.device.online if hasattr(self.device, 'online') else True

    @property
    def today_feeding_quantities(self) -> list[int]:
        return self._data.get("grainStatus", {}).get("todayFeedingQuantities", [])

    @property
    def today_feeding_quantity(self) -> int:
        return self._data.get("grainStatus", {}).get("todayFeedingQuantity", 0)

    @property
    def today_feeding_times(self) -> int:
        return self._data.get("grainStatus", {}).get("todayFeedingTimes", 0)

    @property
    def feeding_plan_state(self) -> bool:
        """Return the state of the feeding plan, based on API data."""
        return bool(self._data.get("enableFeedingPlan", False))

    @property
    def battery_state(self) -> str:
        return cast(str, self._data.get("realInfo", {}).get("batteryState", "unknown"))

    @property
    def food_dispenser_state(self) -> bool:
        return not bool(self._data.get("realInfo", {}).get("grainOutletState", True))

    @property
    def food_low(self) -> bool:
        return not bool(self._data.get("realInfo", {}).get("surplusGrain", True))

    @property
    def unit_type(self) -> int:
        return self._data.get("realInfo", {}).get("unitType", 1)

    @property
    def battery_display_type(self) -> float:
        """Get the battery percentage state."""
        try:
            value = str(self._data.get("realInfo", {}).get("batteryDisplayType", "percentage"))
            # Attempt to convert the value to a float
            return cast(float, float(value))
        except (TypeError, ValueError):
            # Handle the case where the value is None or not a valid float
            return 0.0

    @property
    def online(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("online", False))

    @property
    def running_state(self) -> bool:
        return self._data.get("realInfo", {}).get("runningState", "IDLE") == "RUNNING"

    @property
    def whether_in_sleep_mode(self) -> bool:
        return bool(self._data.get("getAttributeSetting", {}).get("enableSleepMode", False))

    @property
    def enable_low_battery_notice(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("enableLowBatteryNotice", False))

    @property
    def enable_power_change_notice(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("enablePowerChangeNotice", False))

    @property
    def enable_grain_outlet_blocked_notice(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("enableGrainOutletBlockedNotice", False))

    @property
    def device_sn(self) -> str:
        return self._data.get("realInfo", {}).get("deviceSn", "unknown")

    @property
    def mac_address(self) -> str:
        return self._data.get("realInfo", {}).get("mac", "unknown")

    @property
    def wifi_ssid(self) -> str:
        return self._data.get("realInfo", {}).get("wifiSsid", "unknown")

    @property
    def wifi_rssi(self) -> int:
        return self._data.get("realInfo", {}).get("wifiRssi", -100)

    @property
    def electric_quantity(self) -> int:
        return self._data.get("realInfo", {}).get("electricQuantity", 0)

    @property
    def enable_feeding_plan(self) -> bool:
        return self._data.get("realInfo", {}).get("enableFeedingPlan", False)

    @property
    def enable_sound(self) -> bool:
        return self._data.get("realInfo", {}).get("enableSound", False)

    @property
    def enable_light(self) -> bool:
        return self._data.get("realInfo", {}).get("enableLight", False)

    @property
    def light_switch(self) -> bool:
        """Check if the light is enabled."""
        return bool(self._data.get("realInfo", {}).get("lightSwitch", False))

    @property
    def vacuum_state(self) -> bool:
        return self._data.get("realInfo", {}).get("vacuumState", False)

    @property
    def pump_air_state(self) -> bool:
        return self._data.get("realInfo", {}).get("pumpAirState", False)

    @property
    def cover_close_speed(self) -> str:
        return self._data.get("realInfo", {}).get("coverCloseSpeed", "unknown")

    @property
    def enable_re_grain_notice(self) -> bool:
        return self._data.get("realInfo", {}).get("enableReGrainNotice", False)

    @property
    def child_lock_switch(self) -> bool:
        return self._data.get("realInfo", {}).get("childLockSwitch", False)

    @property
    def close_door_time_sec(self) -> int:
        return self._data.get("realInfo", {}).get("closeDoorTimeSec", 0)

    @property
    def screen_display_switch(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("screenDisplaySwitch", False))

    @property
    def resolution(self) -> str:
        """Return the camera resolution."""
        return self._data.get("realInfo", {}).get("resolution", "unknown")

    @property
    def night_vision(self) -> str:
        """Return the current night vision mode."""
        return self._data.get("realInfo", {}).get("nightVision", "unknown")

    @property
    def enable_video_record(self) -> bool:
        """Return whether video recording is enabled."""
        return self._data.get("realInfo", {}).get("enableVideoRecord", False)

    @property
    def video_record_switch(self) -> bool:
        """Return the state of the video recording switch."""
        return self._data.get("realInfo", {}).get("videoRecordSwitch", False)

    @property
    def video_record_mode(self) -> str:
        """Return the current video recording mode."""
        return self._data.get("realInfo", {}).get("videoRecordMode", "unknown")
    
    @property
    def remaining_desiccant(self) -> float | None:
        """Get the remaining desiccant days."""
        value = self._data.get("remainingDesiccantDays")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def last_feed_time(self) -> datetime | None:
        """Return the recordTime of the last successful grain output as a datetime object (UTC)."""
        _LOGGER.debug("last_feed_time called for device: %s", self.serial)
        raw = self._data.get("workRecord", [])

        if not raw or not isinstance(raw, list):
            return None
        
        for day_entry in raw:
            work_records = day_entry.get("workRecords", [])
            for record in work_records:
                if record.get("type") == "GRAIN_OUTPUT_SUCCESS":
                    timestamp_ms = record.get("recordTime", 0)
                    if timestamp_ms:
                        # HA utility: always return UTC datetime
                        dt = dt_util.utc_from_timestamp(timestamp_ms / 1000)
                        _LOGGER.debug("Returning datetime object: %s", dt.isoformat())
                        return dt
        return None

    @property
    def feeding_plan_today_data(self) -> str:
        return self._data.get("getfeedingplantoday", {})

    @property
    def manual_feed_quantity(self):
        if self._manual_feed_quantity is None:
            _LOGGER.warning(f"manual_feed_quantity is None for {self.serial}, setting default to 1.")
            self._manual_feed_quantity = 1  # Default value
        return self._manual_feed_quantity
    
    # Error-handling updated for set_feeding_plan
    async def set_feeding_plan(self, value: bool) -> None:
        _LOGGER.debug(f"Setting feeding plan to {value} for {self.serial}")
        try:
            await self.api.set_feeding_plan(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set feeding plan for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting feeding plan: {err}")

    # Error-handling updated for set_child_lock
    async def set_child_lock(self, value: bool) -> None:
        _LOGGER.debug(f"Setting child lock to {value} for {self.serial}")
        try:
            await self.api.set_child_lock(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set child lock for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting child lock: {err}")

    # Error-handling updated for set_light_enable
    async def set_light_enable(self, value: bool) -> None:
        _LOGGER.debug(f"Setting light enable to {value} for {self.serial}")
        try:
            await self.api.set_light_enable(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set light enable for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting light enable: {err}")

    # Error-handling updated for set_light_switch
    async def set_light_switch(self, value: bool) -> None:
        _LOGGER.debug(f"Setting light switch to {value} for {self.serial}")
        try:
            await self.api.set_light_switch(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set light switch for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting light switch: {err}")

    # Error-handling updated for set_sound_enable
    async def set_sound_enable(self, value: bool) -> None:
        _LOGGER.debug(f"Setting sound enable to {value} for {self.serial}")
        try:
            await self.api.set_sound_enable(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set sound enable for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting sound enable: {err}")

    # Error-handling updated for set_sound_switch
    async def set_sound_switch(self, value: bool) -> None:
        _LOGGER.debug(f"Setting sound switch to {value} for {self.serial}")
        try:
            await self.api.set_sound_switch(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set sound switch for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting sound switch: {err}")

    @manual_feed_quantity.setter
    def manual_feed_quantity(self, value: float):
        """Set the manual feed quantity."""
        _LOGGER.debug(f"Setting manual feed quantity: serial={self.serial}, value={value}")
        self._manual_feed_quantity = value
    
    async def set_manual_feed_quantity(self, value: float):
        """Set the manual feed quantity with a default value handling"""
        _LOGGER.debug(f"Setting manual feed quantity: serial={self.serial}, value={value}")
        self.manual_feed_quantity = max(1, min(value, 12))  # Ensure value is within valid range
        await self.refresh()

    # Method for manual feeding
    async def set_manual_feed(self) -> None:
        _LOGGER.debug(f"Triggering manual feed for {self.serial}")
        try:
            feed_quantity = getattr(self, "manual_feed_quantity", 1)  # Default to 1 if not set
            await self.api.set_manual_feed(self.serial, feed_quantity)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger manual feed for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering manual feed: {err}")

    # Method for setting the feeding plan
    async def set_feeding_plan(self, value: bool) -> None:
        _LOGGER.debug(f"Setting feeding plan to {value} for {self.serial}")
        try:
            await self.api.set_feeding_plan(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set feeding plan for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting feeding plan: {err}")

    # Method for indicator turn on
    async def set_light_on(self) -> None:
        _LOGGER.debug(f"Turning on the indicator for {self.serial}")
        try:
            await self.api.set_light_on(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn on the indicator for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning on the indicator: {err}")

    # Method for indicator turn off
    async def set_light_off(self) -> None:
        _LOGGER.debug(f"Turning off the indicator for {self.serial}")
        try:
            await self.api.set_light_off(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn off the indicator for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning off the indicator: {err}")

    @property
    def update_available(self) -> bool:
        """Return True if an update is available, False otherwise."""
        return bool(self._data.get("getUpgrade", {}).get("jobItemId"))
    
    @property
    def update_release_notes(self) -> str | None:
        """Return release notes if available, else None."""
        upgrade_data = self._data.get("getUpgrade")
        return upgrade_data.get("upgradeDesc") if upgrade_data else None
    
    @property
    def update_version(self) -> str | None:
        """Return target version if available, else None."""
        upgrade_data = self._data.get("getUpgrade")
        return upgrade_data.get("targetVersion") if upgrade_data else None
    
    @property
    def update_name(self) -> str | None:
        """Return update job name if available, else None."""
        upgrade_data = self._data.get("getUpgrade")
        return upgrade_data.get("jobName") if upgrade_data else None
    
    @property
    def update_progress(self) -> float:
        """Return update progress as a float, or 0 if not updating."""
        upgrade_data = self._data.get("getUpgrade")
        if not upgrade_data:
            return 0.0

        progress = upgrade_data.get("progress")
        return float(progress) if progress is not None else 0.0
