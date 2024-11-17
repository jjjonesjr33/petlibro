import aiohttp

from ...api import make_api_call
from aiohttp import ClientSession, ClientError
from ...exceptions import PetLibroAPIError
from ..device import Device
from typing import cast
from logging import getLogger

_LOGGER = getLogger(__name__)

class OneRFIDSmartFeeder(Device):
    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            await super().refresh()  # This calls the refresh method in GranaryFeeder (which also inherits from Device)
    
            # Fetch specific data for this device
            grain_status = await self.api.device_grain_status(self.serial)
            real_info = await self.api.device_real_info(self.serial)
    
            # Update internal data with fetched API data
            self.update_data({
                "grainStatus": grain_status or {},
                "realInfo": real_info or {}
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
        return self._data.get("grainStatus", {}).get("petEatingTime", 0)

    @property
    def feeding_plan_state(self) -> bool:
        """Return the state of the feeding plan, based on API data."""
        return bool(self._data.get("enableFeedingPlan", False))

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

    @property
    def remaining_desiccant(self) -> str:
        """Get the remaining desiccant days."""
        return cast(str, self._data.get("remainingDesiccantDays", "unknown"))
    
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

    # Method for manual feeding
    async def set_manual_feed(self) -> None:
        _LOGGER.debug(f"Triggering manual feed for {self.serial}")
        try:
            await self.api.set_manual_feed(self.serial)
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

    # Method for display matrix turn on
    async def set_display_matrix_on(self) -> None:
        _LOGGER.debug(f"Turning on the display matrix for {self.serial}")
        try:
            await self.api.set_display_matrix_on(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn on the display matrix for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning on the display matrix: {err}")

    # Method for display matrix turn off
    async def set_display_matrix_off(self) -> None:
        _LOGGER.debug(f"Turning off the display matrix for {self.serial}")
        try:
            await self.api.set_display_matrix_off(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to turn off the display matrix for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error turning off the display matrix: {err}")
