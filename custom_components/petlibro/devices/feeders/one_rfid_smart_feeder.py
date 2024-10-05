from typing import cast
from logging import getLogger

from aiohttp import ClientSession, ClientError  # Import aiohttp and ClientError

from .granary_feeder import GranaryFeeder

_LOGGER = getLogger(__name__)

class OneRFIDSmartFeeder(GranaryFeeder):
    async def refresh(self):
        await super().refresh()

        # Fetch data from API
        grain_status = await self.api.device_grain_status(self.serial)
        real_info = await self.api.device_real_info(self.serial)

        # Update internal data
        self.update_data({
            "grainStatus": grain_status or {},
            "realInfo": real_info or {}
        })

    # Property for todayFeedingQuantities (list of quantities fed today)
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
    def today_eating_times(self) -> int:
        return self._data.get("grainStatus", {}).get("todayEatingTimes", 0)

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
    def battery_state(self) -> str:
        return cast(str, self._data.get("realInfo", {}).get("batteryState", "unknown"))

    @property
    def door_state(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("barnDoorState", False))

    # Remove duplicate door_error_state property.
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
    def battery_display_type(self) -> str:
        return cast(str, self._data.get("realInfo", {}).get("batteryDisplayType", "percentage"))

    @property
    def online(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("online", False))

    @property
    def running_state(self) -> bool:
        return self._data.get("realInfo", {}).get("runningState", "IDLE") == "RUNNING"

    @property
    def whether_in_sleep_mode(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("whetherInSleepMode", False))

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

    # Switch methods
    async def set_feeding_plan(self, value: bool) -> None:
        _LOGGER.debug(f"Setting feeding plan to {value} for {self.serial}")
        await self.api.set_feeding_plan(self.serial, value)

    async def set_child_lock(self, value: bool) -> None:
        _LOGGER.debug(f"Setting child lock to {value} for {self.serial}")
        await self.api.set_child_lock(self.serial, value)

    async def set_light_enable(self, value: bool) -> None:
        _LOGGER.debug(f"Setting light enable to {value} for {self.serial}")
        await self.api.set_light_enable(self.serial, value)

    async def set_light_switch(self, value: bool) -> None:
        _LOGGER.debug(f"Setting light switch to {value} for {self.serial}")
        await self.api.set_light_switch(self.serial, value)

    async def set_sound_enable(self, value: bool) -> None:
        _LOGGER.debug(f"Setting sound enable to {value} for {self.serial}")
        await self.api.set_sound_enable(self.serial, value)

    async def set_sound_switch(self, value: bool) -> None:
        _LOGGER.debug(f"Setting sound switch to {value} for {self.serial}")
        await self.api.set_sound_switch(self.serial, value)
