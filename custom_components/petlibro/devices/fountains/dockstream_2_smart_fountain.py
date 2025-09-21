import aiohttp

from ...api import make_api_call
from aiohttp import ClientSession, ClientError
from ...exceptions import PetLibroAPIError
from ..device import Device
from typing import cast
from logging import getLogger

_LOGGER = getLogger(__name__)

class Dockstream2SmartFountain(Device):
    """Represents the Dockstream 2 Smart Fountain device."""

    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            await super().refresh()  # Call the refresh method from the parent class (Device)
        
            # Fetch real info from the API
            real_info = await self.api.device_real_info(self.serial)
            data_real_info = await self.api.device_data_real_info(self.serial)
            attribute_settings = await self.api.device_attribute_settings(self.serial)
            get_upgrade = await self.api.get_device_upgrade(self.serial)
            get_work_record = await self.api.get_device_work_record(self.serial)
            get_feeding_plan_today = await self.api.device_feeding_plan_today_new(self.serial)
            get_drink_water = await self.api.get_device_drink_water(self.serial)

            # Update internal data with fetched API data
            self.update_data({
                "realInfo": real_info or {},
                "dataRealInfo": data_real_info or {},
                "getDrinkWater": get_drink_water or {},
                "getAttributeSetting": attribute_settings or {},
                "getUpgrade": get_upgrade or {},
                "getfeedingplantoday": get_feeding_plan_today or {},
                "workRecord": get_work_record if get_work_record is not None else []
            })

        except PetLibroAPIError as err:
            _LOGGER.error(f"Error refreshing data for Dockstream2SmartFountain: {err}")

    @property
    def available(self) -> bool:
        _LOGGER.debug(f"Device {self.device.name} availability: {self.device.online}")
        return self.device.online if hasattr(self.device, 'online') else True

    @property
    def device_sn(self) -> str:
        """Return the device serial number."""
        return self._data.get("realInfo", {}).get("deviceSn", "unknown")

    @property
    def wifi_ssid(self) -> str:
        """Return the Wi-Fi SSID of the device."""
        return self._data.get("realInfo", {}).get("wifiSsid", "unknown")

    @property
    def online(self) -> bool:
        """Return the online status of the fountain."""
        return bool(self._data.get("realInfo", {}).get("online", False))
    
    @property
    def wifi_rssi(self) -> int:
        """Get the Wi-Fi signal strength."""
        return self._data.get("realInfo", {}).get("wifiRssi", -100)
    
    @property
    def weight(self) -> float:
        """Get the current weight of the water (in grams)."""
        return self._data.get("realInfo", {}).get("weight", 0.0)
    
    @property
    def weight_percent(self) -> int:
        """Get the current weight percentage of water."""
        return self._data.get("realInfo", {}).get("weightPercent", 0)
    
    @property
    def remaining_filter_days(self) -> int:
        """Get the number of days remaining for the filter replacement."""
        return self._data.get("realInfo", {}).get("remainingReplacementDays", 0)
    
    @property
    def remaining_cleaning_days(self) -> int:
        """Get the number of days remaining for machine cleaning."""
        return self._data.get("realInfo", {}).get("remainingCleaningDays", 0)
    
    @property
    def light_switch(self) -> bool:
        """Check if the light is enabled."""
        return bool(self._data.get("realInfo", {}).get("lightSwitch", False))
    
    @property
    def sound_switch(self) -> bool:
        """Check if the sound is enabled."""
        return self._data.get("realInfo", {}).get("soundSwitch", False)
    
    async def set_light_switch(self, value: bool):
        """Enable or disable the light."""
        await self.api.set_light_switch(self.serial, value)
        await self.refresh()
    
    async def set_sound_switch(self, value: bool):
        """Enable or disable the sound."""
        await self.api.set_sound_switch(self.serial, value)
        await self.refresh()

    @property
    def water_state(self) -> bool:
        """Check if water stop switch is on."""
        return not self._data.get("dataRealInfo", {}).get("waterStopSwitch", False)

    @property
    def water_dispensing_mode(self) -> str:
        """Get current water dispensing mode."""
        real = self._data.get("dataRealInfo", {}) or {}

        # raw values as received
        stop_raw = real.get("waterStopSwitch")
        mode_raw = real.get("useWaterType")

        # coerce to the types we expect
        stop = bool(stop_raw)
        try:
            mode = int(mode_raw) if mode_raw is not None else None
        except (TypeError, ValueError):
            mode = None

        # Decide label
        if stop:
            label = "Off"
        elif mode == 0:
            label = "Flowing Water (Constant)"
        elif mode == 1:
            label = "Intermittent Water (Scheduled)"
        else:
            label = "Unknown"

        return label

    @property
    def water_interval(self) -> float:
        return self._data.get("realInfo", {}).get("useWaterInterval", 0)

    async def set_water_interval(self, value: float) -> None:
        _LOGGER.debug(f"Setting water interval to {value} for {self.serial}")
        try:
            current_mode = self._data.get("realInfo", {}).get("useWaterType", 0)
            current_duration = self._data.get("realInfo", {}).get("useWaterDuration", 0)
            await self.api.set_water_interval(self.serial, value, current_mode, current_duration)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set water interval using {current_mode} & {current_duration} for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting water interval using {current_mode} & {current_duration}: {err}")

    @property
    def water_dispensing_duration(self) -> float:
        return self._data.get("realInfo", {}).get("useWaterDuration", 0)

    async def set_water_dispensing_duration(self, value: float) -> None:
        _LOGGER.debug(f"Setting water dispensing duration to {value} for {self.serial}")
        try:
            current_mode = self._data.get("realInfo", {}).get("useWaterType", 0)
            current_interval = self._data.get("realInfo", {}).get("useWaterInterval", 0)
            await self.api.set_water_dispensing_duration(self.serial, value, current_mode, current_interval)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set water dispensing duration using {current_mode} & {current_interval} for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting water dispensing duration using {current_mode} & {current_interval}: {err}")

    # Not currently supported by the device, API accepts, but device doesnt apply. hoping for future firmware update.
    # @property
    # def water_sensing_delay(self) -> float:
    #     return self._data.get("dataRealInfo", {}).get("sensingWaterDuration", 0)

    # async def set_water_sensing_delay(self, value: float) -> None:
    #     _LOGGER.debug(f"Setting water sensing delay to {value} for {self.serial}")
    #     try:
    #         current_mode = self._data.get("dataRealInfo", {}).get("useWaterType", 0)
    #         await self.api.set_water_sensing_delay(self.serial, value, current_mode)
    #         await self.refresh()  # Refresh the state after the action
    #     except aiohttp.ClientError as err:
    #         _LOGGER.error(f"Failed to set water sensing delay using {current_mode} for {self.serial}: {err}")
    #         raise PetLibroAPIError(f"Error setting water sensing delay using {current_mode}: {err}")

    @property
    def water_low_threshold(self) -> float:
        return self._data.get("dataRealInfo", {}).get("lowWater", 0)

    async def set_water_low_threshold(self, value: float) -> None:
        _LOGGER.debug(f"Setting water low threshold to {value} for {self.serial}")
        try:
            await self.api.set_water_low_threshold(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set water low threshold to {value} for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting water low threshold: {err}")

    @property
    def cleaning_cycle(self) -> float:
        return self._data.get("realInfo", {}).get("machineCleaningFrequency", 0)

    async def set_cleaning_cycle(self, value: float) -> None:
        _LOGGER.debug(f"Setting machine cleaning cycle to {value} for {self.serial}")
        try:
            key = "MACHINE_CLEANING"
            await self.api.set_filter_cycle(self.serial, value, key)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set cleaning cycle using {key} for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting cleaning cycle using {key}: {err}")

    @property
    def filter_cycle(self) -> float:
        return self._data.get("realInfo", {}).get("filterReplacementFrequency", 0)

    async def set_filter_cycle(self, value: float) -> None:
        _LOGGER.debug(f"Setting filter cycle to {value} for {self.serial}")
        try:
            key = "FILTER_ELEMENT"
            await self.api.set_filter_cycle(self.serial, value, key)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set filter cycle using {key} for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting filter cycle using {key}: {err}")

    async def set_cleaning_reset(self) -> None:
        _LOGGER.debug(f"Triggering machine cleaning reset for {self.serial}")
        try:
            await self.api.set_cleaning_reset(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger machine cleaning reset for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering machine cleaning reset: {err}")

    async def set_filter_reset(self) -> None:
        _LOGGER.debug(f"Triggering filter reset for {self.serial}")
        try:
            await self.api.set_filter_reset(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger filter reset for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error triggering filter reset: {err}")

    @property
    def power_state(self) -> int:
        api_value = self._data.get("dataRealInfo", {}).get("powerType", 0)
        
        # Direct mapping inside the property
        if api_value == 2:
            return False
        elif api_value == 3:
            return True
        else:
            return "Unknown"

    @property
    def today_drinking_amount(self) -> int:
        """Get the total milliliters of water used today."""
        return self._data.get("getDrinkWater", {}).get("todayTotalMl", 0)
    
    @property
    def today_drinking_count(self) -> int:
        """Get the total count of times drank today."""
        return self._data.get("getDrinkWater", {}).get("todayTotalTimes", 0)

    @property
    def today_drinking_time(self) -> int:
        """Get the total time spent drinking today."""
        return self._data.get("getDrinkWater", {}).get("petEatingTime", 0)

    @property
    def today_avg_time(self) -> int:
        """Get the average time spent drinking in a session today."""
        return self._data.get("getDrinkWater", {}).get("avgDrinkDuration", 0)

    @property
    def yesterday_drinking_amount(self) -> int:
        """Get the total milliliters of water used yesterday."""
        return self._data.get("getDrinkWater", {}).get("yesterdayTotalMl", 0)
    
    @property
    def yesterday_drinking_count(self) -> int:
        """Get the total count of times drank yesterday."""
        return self._data.get("getDrinkWater", {}).get("yesterdayTotalTimes", 0)

    @property
    def filter_replacement_frequency(self) -> int:
        """Get the filter replacement frequency."""
        return self._data.get("realInfo", {}).get("filterReplacementFrequency", 0)
    
    @property
    def machine_cleaning_frequency(self) -> int:
        """Get the machine cleaning frequency."""
        return self._data.get("realInfo", {}).get("machineCleaningFrequency", 0)

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