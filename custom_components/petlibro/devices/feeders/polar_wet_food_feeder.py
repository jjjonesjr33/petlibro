import aiohttp

from ...api import make_api_call
from aiohttp import ClientSession, ClientError
from datetime import datetime
from ...exceptions import PetLibroAPIError
from ..device import Device
from typing import cast
from logging import getLogger

_LOGGER = getLogger(__name__)

class PolarWetFoodFeeder(Device):
    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            await super().refresh()  # This calls the refresh method in GranaryFeeder (which also inherits from Device)
    
            # Fetch specific data for this device
            grain_status = await self.api.device_grain_status(self.serial)
            real_info = await self.api.device_real_info(self.serial)
            wet_list = await self.api.device_wet_feeding_plan_wet_list(self.serial)
    
            # Update internal data with fetched API data
            self.update_data({
                "grainStatus": grain_status or {},
                "realInfo": real_info or {},
                "wetList": wet_list or {},
            })
        except PetLibroAPIError as err:
            _LOGGER.error(f"Error refreshing data for PolarWetFoodFeeder: {err}")

    @property
    def available(self) -> bool:
        _LOGGER.debug(f"Device {self.device.name} availability: {self.device.online}")
        return self.device.online if hasattr(self.device, 'online') else True

    @property
    def battery_state(self) -> str:
        return cast(str, self._data.get("batteryState", "unknown"))  # Battery status is low or unknown
    
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
    def device_sn(self) -> str:
        """Returns the serial number of the device."""
        return self._data.get("deviceSn", "unknown")

    @property
    def door_blocked(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("barnDoorError", False))

    @property
    def electric_quantity(self) -> int:
        """Electric quantity (battery percentage or power state)."""
        return self._data.get("electricQuantity", 0)

    @property
    def feeding_plan_state(self) -> bool:
        """Return the state of the feeding plan."""
        return bool(self._data.get("enableFeedingPlan", False))

    @property
    def food_low(self) -> bool:
        return not bool(self._data.get("surplusGrain", True))  # Surplus grain available

    @property
    def mac_address(self) -> str:
        """Returns the MAC address of the device."""
        return self._data.get("mac", "unknown")

    @property
    def next_feeding_day(self) -> str:
        """Returns the next feeding day."""
        return self._data.get("nextFeedingDay", "unknown")

    @property
    def next_feeding_time(self) -> str:
        """Returns the next feeding start time in AM/PM format."""
        raw_time = self._data.get("nextFeedingTime", "unknown")
        if raw_time == "unknown":
            return raw_time
        try:
            # Convert 24-hour time to 12-hour format with AM/PM
            time_obj = datetime.strptime(raw_time, "%H:%M")
            return time_obj.strftime("%I:%M %p")  # "08:00 AM" or "11:00 PM"
        except ValueError:
            return "Invalid time"

    @property
    def next_feeding_end_time(self) -> str:
        """Returns the next feeding end time in AM/PM format."""
        raw_time = self._data.get("nextFeedingEndTime", "unknown")
        if raw_time == "unknown":
            return raw_time
        try:
            # Convert 24-hour time to 12-hour format with AM/PM
            time_obj = datetime.strptime(raw_time, "%H:%M")
            return time_obj.strftime("%I:%M %p")  # "08:00 AM" or "11:00 PM"
        except ValueError:
            return "Invalid time"
        
    @property
    def manual_feed_id(self) -> int:
        """Returns the manual feed ID."""
        return self._data.get("wetList", {}).get("manualFeedId", None)
        
    @property
    def manual_feed_now(self) -> bool:
        """Returns whether the feeder is set to feed now or not."""
        return self.manual_feed_id is not None

    @property
    def online(self) -> bool:
        """Returns the online status of the device."""
        return self._data.get("online", False)

    @property
    def online_list(self) -> list:
        """Returns a list of online status records with timestamps."""
        return self._data.get("realInfo", {}).get("onlineList", [])

    @property
    def plate_position(self) -> int:
        """Returns the current position of the plate, if applicable."""
        return self._data.get("realInfo", {}).get("platePosition", 0)

    @property
    def temperature(self) -> float:
        """Returns the current temperature in Fahrenheit, rounded to 1 decimal place."""
        celsius = self._data.get("realInfo", {}).get("temperature", 0.0)
        fahrenheit = celsius * 9 / 5 + 32
        return round(fahrenheit, 1)  # Round to 1 decimal place

    @property
    def unit_type(self) -> int:
        return self._data.get("realInfo", {}).get("unitType", 1)

    @property
    def whether_in_sleep_mode(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("whetherInSleepMode", False))

    @property
    def enable_low_battery_notice(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("enableLowBatteryNotice", False))
    
    @property
    def wifi_rssi(self) -> int:
        return self._data.get("wifiRssi", -100)  # WiFi signal strength

    @property
    def wifi_ssid(self) -> str:
        return self._data.get("realInfo", {}).get("wifiSsid", "unknown")

    async def set_manual_feed_now(self, start: bool) -> None:
        try:
            if start:
                _LOGGER.debug(f"Triggering manual feed now for {self.serial}")
                await self.api.set_manual_feed_now(self.serial)
            else:
                _LOGGER.debug(f"Triggering stop feed now for {self.serial}")
                await self.api.set_stop_feed_now(self.serial, self.manual_feed_id)
            
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger manual feed now for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering manual feed now: {err}")

    async def rotate_food_bowl(self) -> None:
        _LOGGER.debug(f"Triggering rotate food bowl for {self.serial}")

        try:
            await self.api.set_rotate_food_bowl(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger rotate food bowl for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering rotate food bowl: {err}")

    async def feed_audio(self) -> None:
        _LOGGER.debug(f"Triggering feed audio for {self.serial}")

        try:
            await self.api.set_feed_audio(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger feed audio for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering feed audio: {err}")