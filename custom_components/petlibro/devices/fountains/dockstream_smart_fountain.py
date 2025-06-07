import aiohttp

from ...api import make_api_call
from aiohttp import ClientSession, ClientError
from ...exceptions import PetLibroAPIError
from ..device import Device
from typing import cast
from logging import getLogger

_LOGGER = getLogger(__name__)

class DockstreamSmartFountain(Device):
    """Represents the Dockstream Smart Fountain device."""

    async def refresh(self):
        """Refresh the device data from the API."""
        await super().refresh()  # Call the refresh method from the parent class (Device)
        
        # Fetch real info from the API
        real_info = await self.api.device_real_info(self.serial)

        # Update internal data with fetched API data
        self.update_data({
            "realInfo": real_info or {}
        })

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
    def vacuum_state(self) -> bool:
        """Check if the vacuum state is active."""
        return self._data.get("realInfo", {}).get("vacuumState", False)
    
    @property
    def pump_air_state(self) -> bool:
        """Check if the air pump is active."""
        return self._data.get("realInfo", {}).get("pumpAirState", False)
    
    @property
    def barn_door_error(self) -> bool:
        """Check if there's a barn door error."""
        return self._data.get("realInfo", {}).get("barnDoorError", False)
    
    @property
    def running_state(self) -> str:
        """Get the current running state of the device."""
        return self._data.get("realInfo", {}).get("runningState", "unknown")
    
    @property
    def light_switch(self) -> bool:
        """Check if the light is enabled."""
        return self._data.get("realInfo", {}).get("lightSwitch", False)
    
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
    
    async def set_manual_cleaning(self):
        """Trigger manual cleaning action."""
        await self.api.set_manual_cleaning(self.serial)
        await self.refresh()

    @property
    def water_dispensing_mode(self) -> int:
        """Return the user-friendly water dispensing mode (mapped directly from the API value)."""
        api_value = self._data.get("realInfo", {}).get("useWaterType", 0)
        
        # Direct mapping inside the property
        if api_value == 0:
            return "Flowing Water (Constant)"
        elif api_value == 1:
            return "Intermittent Water (Scheduled)"
        else:
            return "Unknown"

    async def set_water_dispensing_mode(self, value: int) -> None:
        _LOGGER.debug(f"Setting water dispensing mode to {value} for {self.serial}")
        try:
            await self.api.set_water_dispensing_mode(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set water dispensing mode for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error setting water dispensing mode: {err}")

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

    @property
    def today_total_ml(self) -> int:
        """Get the total milliliters of water used today."""
        return self._data.get("realInfo", {}).get("todayTotalMl", 0)
    
    @property
    def use_water_interval(self) -> int:
        """Get the water usage interval."""
        return self._data.get("realInfo", {}).get("useWaterInterval", 0)
    
    @property
    def use_water_duration(self) -> int:
        """Get the water usage duration."""
        return self._data.get("realInfo", {}).get("useWaterDuration", 0)
    
    @property
    def filter_replacement_frequency(self) -> int:
        """Get the filter replacement frequency."""
        return self._data.get("realInfo", {}).get("filterReplacementFrequency", 0)
    
    @property
    def machine_cleaning_frequency(self) -> int:
        """Get the machine cleaning frequency."""
        return self._data.get("realInfo", {}).get("machineCleaningFrequency", 0)
