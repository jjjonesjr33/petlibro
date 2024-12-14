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
    
            # Update internal data with fetched API data
            self.update_data({
                "grainStatus": grain_status or {},
                "realInfo": real_info or {}
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
    def enable_low_battery_notice(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("enableLowBatteryNotice", False))
    
    @property
    def wifi_rssi(self) -> int:
        return self._data.get("wifiRssi", -100)  # WiFi signal strength

    @property
    def wifi_ssid(self) -> str:
        return self._data.get("realInfo", {}).get("wifiSsid", "unknown")
