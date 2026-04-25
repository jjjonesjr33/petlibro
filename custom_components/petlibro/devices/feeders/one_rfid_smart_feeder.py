import ast
from zoneinfo import ZoneInfo
import aiohttp

from ...api import make_api_call
from aiohttp import ClientSession, ClientError
from ...exceptions import PetLibroAPIError
from ..device import Device
from typing import cast
from logging import getLogger
from datetime import datetime, timedelta, time
from homeassistant.util import dt as dt_util

_LOGGER = getLogger(__name__)

class OneRFIDSmartFeeder(Device):
    def __init__(self, *args, **kwargs):
        """Initialize the feeder with default values."""
        super().__init__(*args, **kwargs)
        self._manual_feed_quantity = None  # Default to None initially

    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            await super().refresh()  # This calls the refresh method in GranaryFeeder (which also inherits from Device)
    
            # Fetch specific data for this device
            grain_status = await self.api.device_grain_status(self.serial)
            real_info = await self.api.device_real_info(self.serial)
            get_upgrade = await self.api.get_device_upgrade(self.serial)
            attribute_settings = await self.api.device_attribute_settings(self.serial)
            get_default_matrix = await self.api.get_default_matrix(self.serial)
            get_work_record = await self.api.get_device_work_record(self.serial)
            get_feeding_plan_today = await self.api.device_feeding_plan_today_new(self.serial)
            feeding_plan_list = (await self.api.device_feeding_plan_list(self.serial)
                if self._data.get("enableFeedingPlan") else [])
            # Update internal data with fetched API data
            self.update_data({
                "grainStatus": grain_status or {},
                "realInfo": real_info or {},
                "getUpgrade": get_upgrade or {},
                "getAttributeSetting": attribute_settings or {},
                "getDefaultMatrix": get_default_matrix or {},
                "getfeedingplantoday": get_feeding_plan_today or {},
                "feedingPlan": feeding_plan_list or [],
                "workRecord": get_work_record if get_work_record is not None else [],
            })
        except PetLibroAPIError as err:
            _LOGGER.error(f"Error refreshing data for OneRFIDSmartFeeder: {err}")

    @property
    def available(self) -> bool:
        _LOGGER.debug(f"Device {self.device.name} availability: {self.device.online}")
        return self.device.online if hasattr(self.device, 'online') else True

    @property
    def today_feeding_quantities(self) -> list[int]:
        return self._data.get("grainStatus", {}).get("todayFeedingQuantities", [])

    @property
    def today_feeding_quantity(self) -> float:
        quantity = self._data.get("grainStatus", {}).get("todayFeedingQuantity")
        return quantity if isinstance(quantity, (int, float)) else 0

    @property
    def today_feeding_times(self) -> int:
        times = self._data.get("grainStatus", {}).get("todayFeedingTimes")
        return times if isinstance(times, int) else 0

    @property
    def today_eating_times(self) -> int:
        return self._data.get("grainStatus", {}).get("todayEatingTimes", 0)

    @property
    def today_eating_time(self) -> int:
        return self._data.get("grainStatus", {}).get("petEatingTime", 0)

    @property
    def feeding_plan_state(self) -> bool:
        """Return the state of the feeding plan, based on API data."""
        return bool(self._data.get("enableFeedingPlan", False))

    @property
    def today_feeding_plan_state(self) -> bool:
        """Return True if all of today's plans are skipped."""
        return bool(self.feeding_plan_today_data.get("allSkipped", False))

    @property
    def battery_state(self) -> str:
        return cast(str, self._data.get("realInfo", {}).get("batteryState", "unknown"))

    @property
    def door_state(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("barnDoorState", False))

    @property
    def food_dispenser_state(self) -> bool:
        return not bool(self._data.get("realInfo", {}).get("grainOutletState", True))

    @property
    def door_blocked(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("barnDoorError", False))

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
        wifi_rssi = self._data.get("realInfo", {}).get("wifiRssi")
        return wifi_rssi if isinstance(wifi_rssi, int) else -100

    @property
    def electric_quantity(self) -> float:
        quantity = self._data.get("realInfo", {}).get("electricQuantity")
        return quantity if isinstance(quantity, (float, int)) else 0

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
        time_sec = self._data.get("realInfo", {}).get("closeDoorTimeSec")
        return time_sec if isinstance(time_sec, int) else 0

    @property
    def display_switch(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("screenDisplaySwitch", False))

    @property
    def child_lock_switch(self) -> bool:
        return not self._data.get("realInfo", {}).get("childLockSwitch", False)

    @property
    def remaining_desiccant(self) -> float | None:
        """Get the remaining desiccant days."""
        value = self._data.get("remainingDesiccantDays")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
    @property
    def desiccant_cycle(self) -> float:
        return self._data.get("realInfo", {}).get("changeDesiccantFrequency", 0)
    
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
    def last_feed_quantity(self) -> int:
        """Return the last feed amount."""
        raw = self._data.get("workRecord", [])
        if raw and isinstance(raw, list):
            for day_entry in raw:
                for record in day_entry.get("workRecords", []):
                    _LOGGER.debug("Evaluating record type: %s", record.get("type"))
                    if record.get("type") == "GRAIN_OUTPUT_SUCCESS":
                        actualGrainNum = record.get("actualGrainNum")
                        return actualGrainNum if isinstance(actualGrainNum, int) else 0
        return 0

    @property
    def feeding_plan_today_data(self) -> dict:
        return self._data.get("getfeedingplantoday", {})

    @property
    def feeding_plan_data(self) -> dict:
        """Return the feeding plan data dictionary."""
        return {
            str(plan["id"]): plan
            for plan in self._data.get("feedingPlan", [])
            if isinstance(plan, dict) and "id" in plan
        } or {}
    
    @property
    def get_next_feed(self) -> dict:
        """Get the next scheduled feeding plan.

        :Returns: {
                "id": int,
                "utc_time": datetime,
            }
        """
        now_utc = dt_util.now(dt_util.UTC)
        next_feed = {}
        
        for feed in self.feeding_plan_data.values():
            feed: dict
            
            if not (feed.get("id") and feed.get("enable") and ":" in feed.get("executionTime", "")):
                continue
                
            timezone = ZoneInfo(feed.get("timezone", "UTC"))
            repeat_days = ast.literal_eval(feed.get("repeatDay", ""))
            now_local = now_utc.astimezone(timezone)
            hour, minute = map(int, feed["executionTime"].split(":"))
            
            if not repeat_days:
                plan_dt_local = datetime.combine(now_local.date(), time(hour, minute), timezone)
                if plan_dt_local > now_local:
                    candidate_dt_local = plan_dt_local # today
                else:
                    candidate_dt_local = plan_dt_local + timedelta(days=1) # tomorrow
            else:
                for i in range(8): # 0-7 days ahead
                    day_dt_local = now_local + timedelta(days=i)
                    if day_dt_local.isoweekday() not in repeat_days:
                        continue

                    plan_dt_local = datetime.combine(day_dt_local.date(), time(hour, minute), timezone)
                    if plan_dt_local > now_local:
                        candidate_dt_local = plan_dt_local
                        break
                    
            if candidate_dt_local:
                candidate_dt_utc = candidate_dt_local.astimezone(dt_util.UTC)
                if not next_feed or candidate_dt_utc < next_feed["utc_time"]:
                    next_feed = {
                        "id": feed["id"],
                        "utc_time": candidate_dt_utc,
                    }
        return next_feed

    @property
    def next_feed_time(self) -> datetime | None:
        """Return the next scheduled feed time as a datetime object (UTC)."""
        _LOGGER.debug("next_feed_time called for device: %s", self.serial)
        
        next_feed = self.get_next_feed.copy()
        if next_feed and (utc_time := next_feed.get("utc_time")):
            _LOGGER.debug("Returning datetime object: %s", utc_time.isoformat())
            return utc_time
        return None

    @property
    def next_feed_quantity(self) -> int:
        """Return the next scheduled feed amount."""
        next_feed = self.get_next_feed.copy()
        if next_feed and (plan_id := next_feed.get("id")):
            feeding_plan = self.feeding_plan_data.get(str(plan_id), {})
            if feeding_plan:
                grainNum = feeding_plan.get("grainNum")
                return grainNum if isinstance(grainNum, int) else 0
        return 0

    @property
    def manual_feed_quantity(self):
        if self._manual_feed_quantity is None:
            _LOGGER.warning(f"manual_feed_quantity is None for {self.serial}, setting default to 1.")
            self._manual_feed_quantity = 1  # Default value
        return self._manual_feed_quantity

    async def set_desiccant_cycle(self, value: float) -> None:
        _LOGGER.debug(f"Setting desiccant cycle to {value} for {self.serial}")
        try:
            key = "DESSICANT"
            await self.api.set_desiccant_cycle(self.serial, value, key)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set desiccant cycle for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting desiccant cycle: {err}")

    @property
    def sound_switch(self) -> bool:
        return self._data.get("realInfo", {}).get("soundSwitch", False)

    @property
    def sound_level(self) -> float:
        return self._data.get("getAttributeSetting", {}).get("volume", 0)

    async def set_sound_level(self, value: float) -> None:
        _LOGGER.debug(f"Setting sound level to {value} for {self.serial}")
        try:
            await self.api.set_sound_level(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set sound level for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting sound level: {err}")

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
        self.manual_feed_quantity = max(1, min(value, self.max_feed_portions))  # Ensure value is within valid range

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

    # Method for manual lid opening
    async def set_manual_lid_open(self) -> None:
        _LOGGER.debug(f"Triggering manual lid opening for {self.serial}")
        try:
            await self.api.set_manual_lid_open(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger manual lid opening for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering manual lid opening: {err}")

    # Method for display turn on
    async def set_display_on(self) -> None:
        _LOGGER.debug(f"Turning on the display matrix for {self.serial}")
        try:
            await self.api.set_display_on(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn on the display for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning on the display: {err}")

    # Method for display matrix turn off
    async def set_display_off(self) -> None:
        _LOGGER.debug(f"Turning off the display for {self.serial}")
        try:
            await self.api.set_display_off(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn off the display for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning off the display: {err}")

    # Method for sound turn on
    async def set_sound_on(self) -> None:
        _LOGGER.debug(f"Turning on the sound for {self.serial}")
        try:
            await self.api.set_sound_on(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn on the sound for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning on the sound: {err}")

    # Method for sound turn off
    async def set_sound_off(self) -> None:
        _LOGGER.debug(f"Turning off the sound for {self.serial}")
        try:
            await self.api.set_sound_off(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn off the sound for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning off the sound: {err}")

    async def set_desiccant_reset(self) -> None:
        _LOGGER.debug(f"Triggering desiccant reset for {self.serial}")
        try:
            await self.api.set_desiccant_reset(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger desiccant reset for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering desiccant reset: {err}")

    @property
    def lid_speed(self) -> str:
        """Return the user-friendly lid speed (mapped directly from the API value)."""
        api_value = self._data.get("getAttributeSetting", {}).get("coverCloseSpeed", "FAST")
        
        # Direct mapping inside the property
        if api_value == "FAST":
            return "Fast"
        elif api_value == "MEDIUM":
            return "Medium"
        elif api_value == "SLOW":
            return "Slow"
        else:
            return "Unknown"

    async def set_lid_speed(self, value: str) -> None:
        _LOGGER.debug(f"Setting lid speed to {value} for {self.serial}")
        try:
            await self.api.set_lid_speed(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set lid speed for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting lid speed: {err}")

    @property
    def lid_mode(self) -> str:
        """Return the user-friendly lid mode (mapped directly from the API value)."""
        api_value = self._data.get("getAttributeSetting", {}).get("coverOpenMode", "CUSTOM")
        
        # Direct mapping inside the property
        if api_value == "KEEP_OPEN":
            return "Open Mode (Stays Open Until Closed)"
        elif api_value == "CUSTOM":
            return "Personal Mode (Opens on Detection)"
        else:
            return "Unknown"

    async def set_lid_mode(self, value: str) -> None:
        _LOGGER.debug(f"Setting lid mode to {value} for {self.serial}")
        try:
            await self.api.set_lid_mode(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set lid mode for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting lid mode: {err}")

    @property
    def lid_close_time(self) -> float:
        return self._data.get("getAttributeSetting", {}).get("closeDoorTimeSec", 0)

    async def set_lid_close_time(self, value: float) -> None:
        _LOGGER.debug(f"Setting lid close time to {value} for {self.serial}")
        try:
            await self.api.set_lid_close_time(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set lid close time for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting lid close time: {err}")
    
    @property
    def display_text(self) -> str:
        """Return the current display text from local data."""
        return self._data.get("getDefaultMatrix", {}).get("screenLetter", "ERROR")

    async def set_display_text(self, value: str) -> None:
        _LOGGER.debug(f"Setting display text to {value} for {self.serial}")
        try:
            await self.api.set_display_text(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set display text for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting display text: {err}")

    @property
    def display_icon(self) -> float:
        """Return the user-friendly display icon (mapped directly from the API value)."""
        api_value = self._data.get("getDefaultMatrix", {}).get("screenDisplayId", None)
        
        # Direct mapping inside the property
        if api_value == 5:
            return "Heart"
        elif api_value == 6:
            return "Dog"
        elif api_value == 7:
            return "Cat"
        elif api_value == 8:
            return "Elk"
        else:
            return "Unknown"

    async def set_display_icon(self, value: float) -> None:
        _LOGGER.debug(f"Setting display icon to {value} for {self.serial}")
        try:
            await self.api.set_display_icon(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set display icon for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting display icon: {err}")

    @property
    def display_selection(self) -> str:
        display_text = self._data.get("getDefaultMatrix", {}).get("screenLetter", None)
        display_icon = self._data.get("getDefaultMatrix", {}).get("screenDisplayId", None)

        if isinstance(display_text, str):
            return f"Displaying Text: {display_text}"
        
        if isinstance(display_icon, int):
            icon_map = {
                5: "Heart",
                6: "Dog",
                7: "Cat",
                8: "Elk",
            }
            return f"Displaying Icon: {icon_map.get(display_icon, 'Unknown')}"

        return "No valid display data found"

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
