"""Petlibro Polar Smart Wet Food Feeder."""

import asyncio
from datetime import datetime
from logging import getLogger
from typing import cast

import aiohttp

from ...exceptions import PetLibroAPIError
from .wet_food_feeder import WetFoodFeeder

_LOGGER = getLogger(__name__)


class PolarWetFoodFeeder(WetFoodFeeder):
    """Petlibro Polar Smart Wet Food Feeder."""

    async def refresh(self) -> None:
        """Refresh the device data from the API."""
        try:
            await super().refresh()  # This calls the refresh method in GranaryFeeder (which also inherits from Device)

            # Fetch specific data for this device
            grain_status = await self.api.device_grain_status(self.serial)
            real_info = await self.api.device_real_info(self.serial)
            attribute_settings = await self.api.device_attribute_settings(self.serial)
            get_upgrade = await self.api.get_device_upgrade(self.serial)
            wet_feeding_plan = await self.api.device_wet_feeding_plan(self.serial)
            get_feeding_plan_today = await self.api.device_feeding_plan_today_new(
                self.serial
            )

            # Update internal data with fetched API data
            self.update_data(
                {
                    "grainStatus": grain_status or {},
                    "realInfo": real_info or {},
                    "getAttributeSetting": attribute_settings or {},
                    "getUpgrade": get_upgrade or {},
                    "wetFeedingPlan": wet_feeding_plan or {},
                    "getfeedingplantoday": get_feeding_plan_today or {},
                }
            )
        except PetLibroAPIError:
            _LOGGER.exception("Error refreshing data for PolarWetFoodFeeder")

    @property
    def available(self) -> bool:
        """Return `True` if the device is available."""
        _LOGGER.debug("Device %s availability: %s", self.name, self.online)
        return self.online if hasattr(self, "online") else True

    @property
    def battery_state(self) -> str:
        """Return the battery state."""
        return cast(
            "str", self._data.get("batteryState", "unknown")
        )  # Battery status is low or unknown

    @property
    def battery_display_type(self) -> float:
        """Get the battery percentage state."""
        try:
            value = str(
                self._data.get("realInfo", {}).get("batteryDisplayType", "percentage")
            )
            # Attempt to convert the value to a float
            return cast("float", float(value))
        except (TypeError, ValueError):
            # Handle the case where the value is None or not a valid float
            return 0.0

    @property
    def device_sn(self) -> str:
        """Return the device serial number."""
        return self._data.get("deviceSn", "unknown")

    @property
    def door_blocked(self) -> bool:
        """Return `True` if the door is blocked."""
        return bool(self._data.get("realInfo", {}).get("barnDoorError", False))

    @property
    def electric_quantity(self) -> float:
        """Electric quantity (battery percentage or power state)."""
        quantity = self._data.get("electricQuantity")
        return quantity if isinstance(quantity, (float, int)) else 0

    @property
    def feeding_plan_state(self) -> bool:
        """Return the state of the feeding plan."""
        return bool(self._data.get("enableFeedingPlan", False))

    @property
    def food_low(self) -> bool:
        """Return `True` if the food is low."""
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
        return self._data.get("wetFeedingPlan", {}).get("manualFeedId", None)

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
        """Return the unit type."""
        return self._data.get("realInfo", {}).get("unitType", 1)

    @property
    def whether_in_sleep_mode(self) -> bool:
        """Return `True` if the device is in sleep mode."""
        return bool(
            self._data.get("getAttributeSetting", {}).get("enableSleepMode", False)
        )

    @property
    def enable_low_battery_notice(self) -> bool:
        """Return `True` if the low battery notice is enabled."""
        return bool(self._data.get("realInfo", {}).get("enableLowBatteryNotice", False))

    @property
    def wifi_rssi(self) -> int:
        """Return the Wi-Fi RSSI."""
        wifi_rssi = self._data.get("wifiRssi")
        return wifi_rssi if isinstance(wifi_rssi, int) else -100  # WiFi signal strength

    @property
    def wifi_ssid(self) -> str:
        """Return the Wi-Fi SSID."""
        return self._data.get("realInfo", {}).get("wifiSsid", "unknown")

    @property
    def feeding_plan_today_data(self) -> str:
        """Return today's feeding plan data."""
        return self._data.get("getfeedingplantoday", {})

    @property
    def light_switch(self) -> bool:
        """Check if the light is enabled."""
        return bool(self._data.get("realInfo", {}).get("lightSwitch", False))

    async def set_manual_feed_now(self, start: bool, plate: int) -> None:
        """Set manual feed now."""
        plate = plate if plate is not None else self.plate_position
        try:
            if start:
                _LOGGER.debug(
                    "Triggering manual feed now for %s with plate no.%s",
                    self.serial,
                    plate,
                )
                await self.api.set_manual_feed_now(self.serial, plate)
            else:
                _LOGGER.debug("Triggering stop feed now for %s", self.serial)
                await self.api.set_stop_feed_now(self.serial, self.manual_feed_id)

            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to trigger manual feed now for %s with plate no.%s",
                self.serial,
                plate,
            )
            msg = f"Error triggering manual feed now: {err}"
            raise PetLibroAPIError(msg) from err

    async def set_plate_position(self, value: str | int) -> None:
        """Rotate bowl to requested plate (1-3)."""
        try:
            target = int(value)
        except (TypeError, ValueError) as err:
            msg = f"Invalid plate value: {value!r}"
            raise PetLibroAPIError(msg) from err
        if target not in (1, 2, 3):
            # Raise an error if plate count somehow became less than 1 or more than 3.
            msg = f"Plate must be 1, 2, or 3, got {target}"
            raise PetLibroAPIError(msg)

        # Ensure we know current position
        if not self.plate_position:
            await self.refresh()
        curr = self.plate_position or 1

        steps = (target - curr) % 3
        _LOGGER.debug(
            "Rotate-to-plate: curr=%s target=%s steps=%s for %s",
            curr,
            target,
            steps,
            self.serial,
        )

        # didnt test other cooldowns, may be able reduce.
        rotate_cooldown = 0.6
        for _ in range(steps):
            await self.api.set_rotate_food_bowl(self.serial)
            await asyncio.sleep(rotate_cooldown)
            await self.refresh()

        # Final refresh so sensor/current_option show the target
        await self.refresh()

    async def rotate_food_bowl(self) -> None:
        """Rotate food bowl."""
        _LOGGER.debug("Triggering rotate food bowl for %s", self.serial)

        try:
            await self.api.set_rotate_food_bowl(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception("Failed to trigger rotate food bowl for %s", self.serial)
            msg = f"Error triggering rotate food bowl: {err}"
            raise PetLibroAPIError(msg) from err

    async def feed_audio(self) -> None:
        """Trigger the feed audio."""
        _LOGGER.debug("Triggering feed audio for %s", self.serial)

        try:
            await self.api.set_feed_audio(self.serial)
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception("Failed to trigger feed audio for %s", self.serial)
            msg = f"Error triggering feed audio: {err}"
            raise PetLibroAPIError(msg) from err

    async def reposition_schedule(self) -> None:
        """Trigger reposition schedule."""
        _LOGGER.debug("Triggering reposition the schedule for %s", self.serial)

        if not self._data.get("wetFeedingPlan"):
            _LOGGER.debug(
                "Triggering device data refresh because wet feeding plan data is missing for %s",
                self.serial,
            )
            # Refresh the state to ensure the wet feeding plan is already fetched
            try:
                await self.refresh()
            except aiohttp.ClientError as err:
                _LOGGER.exception(
                    "Failed to refresh device data for triggering reposition the schedule for %s",
                    self.serial,
                )
                msg = f"Error refresh device data for triggering reposition schedule: {err}"
                raise PetLibroAPIError(msg) from err

        wet_plan = self._data.get("wetFeedingPlan", {})
        plan_name = wet_plan.get("templateName")

        if not plan_name:
            _LOGGER.error("Missing template name in wetFeedingPlan for %s", self.serial)
            msg = "Missing template name in wetFeedingPlan"
            raise PetLibroAPIError(msg)

        plan_data = wet_plan.get("plan", [])
        if not isinstance(plan_data, list):
            _LOGGER.error("Unexpected format for wet feeding plan: %s", plan_data)
            msg = "Invalid wet feeding plan format"
            raise PetLibroAPIError(msg)

        current_feeding_plan = [
            {
                "id": plate.get("id"),
                "plate": plate.get("plate"),
                "label": plate.get("label"),
                "executionStartTime": plate.get("executionStartTime"),
                "executionEndTime": plate.get("executionEndTime"),
            }
            for plate in self._data.get("wetFeedingPlan", {}).get("plan", [])
        ]

        try:
            await self.api.set_reposition_schedule(
                self.serial, current_feeding_plan, plan_name
            )
            await self.refresh()  # Refresh the state after the action
        except aiohttp.ClientError as err:
            _LOGGER.exception(
                "Failed to trigger reposition the schedule for %s", self.serial
            )
            msg = f"Error triggering reposition schedule: {err}"
            raise PetLibroAPIError(msg) from err

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
