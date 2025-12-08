"""Petlibro Dockstream 2 Smart Fountain."""

from logging import getLogger

import aiohttp

from ...exceptions import PetLibroAPIError
from ..device import Device

_LOGGER = getLogger(__name__)


class Dockstream2SmartFountain(Device):
    """Represents the Dockstream 2 Smart Fountain device."""

    async def refresh(self) -> None:
        """Refresh the device data from the API."""
        try:
            await (
                super().refresh()
            )  # Call the refresh method from the parent class (Device)

            # Fetch real info from the API
            real_info = await self.api.device_real_info(self.serial)
            data_real_info = await self.api.device_data_real_info(self.serial)
            attribute_settings = await self.api.device_attribute_settings(self.serial)
            get_upgrade = await self.api.get_device_upgrade(self.serial)
            get_work_record = await self.api.get_device_work_record(self.serial)
            get_feeding_plan_today = await self.api.device_feeding_plan_today_new(
                self.serial
            )
            get_drink_water = await self.api.get_device_drink_water(self.serial)

            # Update internal data with fetched API data
            self.update_data(
                {
                    "realInfo": real_info or {},
                    "dataRealInfo": data_real_info or {},
                    "getDrinkWater": get_drink_water or {},
                    "getAttributeSetting": attribute_settings or {},
                    "getUpgrade": get_upgrade or {},
                    "getfeedingplantoday": get_feeding_plan_today or {},
                    "workRecord": get_work_record
                    if get_work_record is not None
                    else [],
                }
            )

        except PetLibroAPIError:
            _LOGGER.exception("Error refreshing data for Dockstream2SmartFountain")

    @property
    def available(self) -> bool:
        """Return `True` if the device is available."""
        _LOGGER.debug("Device %s availability: %s", self.name, self.online)
        return self.online if hasattr(self, "online") else True

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
        wifi_rssi = self._data.get("realInfo", {}).get("wifiRssi")
        return wifi_rssi if isinstance(wifi_rssi, int) else -100

    @property
    def weight(self) -> float:
        """Get the current weight of the water (in grams)."""
        weight = self._data.get("realInfo", {}).get("weight")
        return weight if isinstance(weight, (int, float)) else 0

    @property
    def weight_percent(self) -> int | float:
        """Get the current weight percentage of water."""
        weight_percent = self._data.get("realInfo", {}).get("weightPercent")
        return weight_percent if isinstance(weight_percent, (int, float)) else 0

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

    async def set_light_switch(self, value: bool) -> None:
        """Enable or disable the light."""
        await self.api.set_light_switch(self.serial, value)
        await self.refresh()

    async def set_sound_switch(self, value: bool) -> None:
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
        """Return the water interval."""
        water_interval = self._data.get("realInfo", {}).get("useWaterInterval")
        return water_interval if isinstance(water_interval, (int, float)) else 0

    async def set_water_interval(self, value: float) -> None:
        """Set the water interval."""
        _LOGGER.debug("Setting water interval to %s for %s", value, self.serial)
        try:
            current_mode = self._data.get("realInfo", {}).get("useWaterType", 0)
            current_duration = self._data.get("realInfo", {}).get("useWaterDuration", 0)
            await self.api.set_water_interval(
                self.serial, value, current_mode, current_duration
            )
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to set water interval using %s & %s for %s",
                current_mode,
                current_duration,
                self.serial,
            )
            msg = f"Error setting water interval using {current_mode} & {current_duration}: {err}"
            raise PetLibroAPIError(msg) from err

    @property
    def water_dispensing_duration(self) -> float:
        """Return the water dispensing duration."""
        duration = self._data.get("realInfo", {}).get("useWaterDuration")
        return duration if isinstance(duration, (int, float)) else 0

    async def set_water_dispensing_duration(self, value: float) -> None:
        """Set the water dispensing duration."""
        _LOGGER.debug(
            "Setting water dispensing duration to %s for %s", value, self.serial
        )
        try:
            current_mode = self._data.get("realInfo", {}).get("useWaterType", 0)
            current_interval = self._data.get("realInfo", {}).get("useWaterInterval", 0)
            await self.api.set_water_dispensing_duration(
                self.serial, value, current_mode, current_interval
            )
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to set water dispensing duration using %s & %s for %s",
                current_mode,
                current_interval,
                self.serial,
            )
            msg = f"Error setting water dispensing duration using {current_mode} & {current_interval}: {err}"
            raise PetLibroAPIError(msg) from err

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
        """Return the water low threshold."""
        threshold = self._data.get("dataRealInfo", {}).get("lowWater")
        return threshold if isinstance(threshold, (int, float)) else 0

    async def set_water_low_threshold(self, value: float) -> None:
        """Set the water low threshold."""
        _LOGGER.debug("Setting water low threshold to %s for %s", value, self.serial)
        try:
            await self.api.set_water_low_threshold(self.serial, value)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to set water low threshold to %s for %s", value, self.serial
            )
            msg = f"Error setting water low threshold: {err}"
            raise PetLibroAPIError(msg) from err

    @property
    def cleaning_cycle(self) -> float:
        """Return the cleaning cycle."""
        cleaning_cycle = self._data.get("realInfo", {}).get("machineCleaningFrequency")
        return cleaning_cycle if isinstance(cleaning_cycle, (int, float)) else 0

    async def set_cleaning_cycle(self, value: float) -> None:
        """Set the cleaning cycle."""
        _LOGGER.debug("Setting machine cleaning cycle to %s for %s", value, self.serial)
        try:
            key = "MACHINE_CLEANING"
            await self.api.set_filter_cycle(self.serial, value, key)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to set cleaning cycle using %s for %s", key, self.serial
            )
            msg = f"Error setting cleaning cycle using {key}: {err}"
            raise PetLibroAPIError(msg) from err

    @property
    def filter_cycle(self) -> float:
        """Return the filter cycle."""
        filter_cycle = self._data.get("realInfo", {}).get("filterReplacementFrequency")
        return filter_cycle if isinstance(filter_cycle, (int, float)) else 0

    async def set_filter_cycle(self, value: float) -> None:
        """Set the filter cycle."""
        _LOGGER.debug("Setting filter cycle to %s for %s", value, self.serial)
        try:
            key = "FILTER_ELEMENT"
            await self.api.set_filter_cycle(self.serial, value, key)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to set filter cycle using %s for %s", key, self.serial
            )
            msg = f"Error setting filter cycle using {key}: {err}"
            raise PetLibroAPIError(msg) from err

    async def set_cleaning_reset(self) -> None:
        """Set cleaning reset."""
        _LOGGER.debug("Triggering machine cleaning reset for %s", self.serial)
        try:
            await self.api.set_cleaning_reset(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to trigger machine cleaning reset for %s", self.serial
            )
            msg = f"Error triggering machine cleaning reset: {err}"
            raise PetLibroAPIError(msg) from err

    async def set_filter_reset(self) -> None:
        """Set filter reset."""
        _LOGGER.debug("Triggering filter reset for %s", self.serial)
        try:
            await self.api.set_filter_reset(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception("Failed to trigger filter reset for %s", self.serial)
            msg = f"Error triggering filter reset: {err}"
            raise PetLibroAPIError(msg) from err

    @property
    def power_state(self) -> int:
        """Return the power state."""
        api_value = self._data.get("dataRealInfo", {}).get("powerType", 0)

        # Direct mapping inside the property
        if api_value == 2:
            return False
        if api_value == 3:
            return True
        return "Unknown"

    @property
    def today_drinking_amount(self) -> float:
        """Get the total milliliters of water used today."""
        amount = self._data.get("getDrinkWater", {}).get("todayTotalMl")
        return amount if isinstance(amount, (int, float)) else 0

    @property
    def today_drinking_count(self) -> int:
        """Get the total count of times drank today."""
        drinking_count = self._data.get("getDrinkWater", {}).get("todayTotalTimes")
        return drinking_count if isinstance(drinking_count, int) else 0

    @property
    def today_drinking_time(self) -> int:
        """Get the total time spent drinking today."""
        drinking_time = self._data.get("getDrinkWater", {}).get("petEatingTime")
        return drinking_time if isinstance(drinking_time, int) else 0

    @property
    def today_avg_time(self) -> int:
        """Get the average time spent drinking in a session today."""
        avg_time = self._data.get("getDrinkWater", {}).get("avgDrinkDuration")
        return avg_time if isinstance(avg_time, int) else 0

    @property
    def yesterday_drinking_amount(self) -> float:
        """Get the total milliliters of water used yesterday."""
        amount = self._data.get("getDrinkWater", {}).get("yesterdayTotalMl")
        return amount if isinstance(amount, (int, float)) else 0

    @property
    def yesterday_drinking_count(self) -> int:
        """Get the total count of times drank yesterday."""
        drinking_count = self._data.get("getDrinkWater", {}).get("yesterdayTotalTimes")
        return drinking_count if isinstance(drinking_count, int) else 0

    @property
    def filter_replacement_frequency(self) -> int:
        """Get the filter replacement frequency."""
        frequency = self._data.get("realInfo", {}).get("filterReplacementFrequency")
        return frequency if isinstance(frequency, int) else 0

    @property
    def machine_cleaning_frequency(self) -> int:
        """Get the machine cleaning frequency."""
        frequency = self._data.get("realInfo", {}).get("machineCleaningFrequency")
        return frequency if isinstance(frequency, int) else 0

    # Method for indicator turn on
    async def set_light_on(self) -> None:
        """Turn the indicator light on."""
        _LOGGER.debug("Turning on the indicator for %s", self.serial)
        try:
            await self.api.set_light_on(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception("Failed to turn on the indicator for %s", self.serial)
            msg = f"Error turning on the indicator: {err}"
            raise PetLibroAPIError(msg) from err

    # Method for indicator turn off
    async def set_light_off(self) -> None:
        """Turn the indicator light off."""
        _LOGGER.debug("Turning off the indicator for %s", self.serial)
        try:
            await self.api.set_light_off(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception("Failed to turn off the indicator for %s", self.serial)
            msg = f"Error turning off the indicator: {err}"
            raise PetLibroAPIError(msg) from err

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
