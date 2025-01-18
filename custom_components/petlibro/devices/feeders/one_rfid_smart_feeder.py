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
            attribute_settings = await self.api.device_attribute_settings(self.serial)
    
            # Update internal data with fetched API data
            self.update_data({
                "grainStatus": grain_status or {},
                "realInfo": real_info or {},
                "getAttributeSetting": attribute_settings or {}
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
    def display_switch(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("screenDisplaySwitch", False))

    @property
    def child_lock_switch(self) -> bool:
        return not self._data.get("realInfo", {}).get("childLockSwitch", False)

    @property
    def remaining_desiccant(self) -> str:
        """Get the remaining desiccant days."""
        return cast(str, self._data.get("remainingDesiccantDays", "unknown"))
    
    @property
    def desiccant_frequency(self) -> float:
        return self._data.get("realInfo", {}).get("changeDesiccantFrequency", 0)

    async def set_desiccant_frequency(self, value: float) -> None:
        _LOGGER.debug(f"Setting desiccant frequency to {value} for {self.serial}")
        try:
            await self.api.set_desiccant_frequency(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set desiccant frequency for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting desiccantfrequency: {err}")
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
    def lid_mode(self) -> str:
        """Return the user-friendly lid mode (mapped directly from the API value)."""
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
            return "Stay Open"
        elif api_value == "CUSTOM":
            return "Open On Detection"
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
        