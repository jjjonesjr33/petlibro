from typing import cast
from logging import getLogger

from .granary_feeder import GranaryFeeder

# Configure the logger
_LOGGER = getLogger(__name__)

class OneRFIDSmartFeeder(GranaryFeeder):
    async def refresh(self):
        await super().refresh()

        # Fetch data from API
        grain_status = await self.api.device_grain_status(self.serial)
        real_info = await self.api.device_real_info(self.serial)

        # Update internal data
        self.update_data({
            "grainStatus": grain_status,
            "realInfo": real_info
        })

    @property
    def today_eating_time(self) -> int:
        eating_time_str = self._data.get("grainStatus", {}).get("eatingTime", "0'0''")
        if not eating_time_str:
            return 0

        try:
            minutes, seconds = map(int, eating_time_str.replace("''", "").split("'"))
            total_seconds = minutes * 60 + seconds
        except ValueError:
            return 0

        return total_seconds

    @property
    def today_eating_times(self) -> int:
        quantity = self._data.get("grainStatus", {}).get("todayEatingTimes")
        if not quantity:
            return 0

        return quantity

    @property
    def battery_state(self) -> str:
        return cast(str, self._data.get("realInfo", {}).get("batteryState"))

    @property
    def door_state(self) -> bool:
        # Accessing the realInfo section from _data
        return bool(self._data.get("realInfo", {}).get("barnDoorState"))

    @property
    def food_dispenser_state(self) -> bool:
        # Accessing the realInfo section from _data
        return not bool(self._data.get("realInfo", {}).get("grainOutletState"))

    @property
    def door_blocked(self) -> bool:
        # Accessing the realInfo section from _data
        return bool(self._data.get("realInfo", {}).get("barnDoorError"))

    @property
    def food_low(self) -> bool:
        # Accessing the realInfo section from _data
        return not bool(self._data.get("realInfo", {}).get("surplusGrain"))

    # New binary sensors for connectivity and state

    @property
    def online(self) -> bool:
        # Check online status from realInfo
        return bool(self._data.get("realInfo", {}).get("online"))

    @property
    def running_state(self) -> bool:
        # Check if device is running from realInfo
        return self._data.get("realInfo", {}).get("runningState") == "RUNNING"

    @property
    def whether_in_sleep_mode(self) -> bool:
        # Check if device is in sleep mode
        return bool(self._data.get("realInfo", {}).get("whetherInSleepMode"))

    @property
    def enable_low_battery_notice(self) -> bool:
        # Check if low battery notice is enabled
        return bool(self._data.get("realInfo", {}).get("enableLowBatteryNotice"))

    @property
    def enable_power_change_notice(self) -> bool:
        # Check if power change notice is enabled
        return bool(self._data.get("realInfo", {}).get("enablePowerChangeNotice"))

    @property
    def enable_grain_outlet_blocked_notice(self) -> bool:
        # Check if grain outlet blocked notice is enabled
        return bool(self._data.get("realInfo", {}).get("enableGrainOutletBlockedNotice"))

    # Switch methods for managing features

    async def set_feeding_plan(self, value: bool) -> None:
        """Enable or disable the feeding plan."""
        _LOGGER.debug(f"Setting feeding plan to {value} for {self.serial}")
        await self.api.set_feeding_plan(self.serial, value)

    async def set_child_lock(self, value: bool) -> None:
        """Enable or disable the child lock."""
        _LOGGER.debug(f"Setting child lock to {value} for {self.serial}")
        await self.api.set_child_lock(self.serial, value)

    async def set_light_enable(self, value: bool) -> None:
        """Enable or disable the light functionality."""
        _LOGGER.debug(f"Setting light enable to {value} for {self.serial}")
        await self.api.set_light_enable(self.serial, value)

    async def set_light_switch(self, value: bool) -> None:
        """Turn the light on or off."""
        _LOGGER.debug(f"Setting light switch to {value} for {self.serial}")
        await self.api.set_light_switch(self.serial, value)

    async def set_sound_enable(self, value: bool) -> None:
        """Enable or disable the sound functionality."""
        _LOGGER.debug(f"Setting sound enable to {value} for {self.serial}")
        await self.api.set_sound_enable(self.serial, value)

    async def set_sound_switch(self, value: bool) -> None:
        """Turn the sound on or off."""
        _LOGGER.debug(f"Setting sound switch to {value} for {self.serial}")
        await self.api.set_sound_switch(self.serial, value)
