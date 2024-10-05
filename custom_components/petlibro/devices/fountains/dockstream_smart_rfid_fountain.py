from ..device import Device

class DockstreamSmartRFIDFountain(Device):
    """Represents the Dockstream Smart RFID Fountain device."""

    async def refresh(self):
        """Refresh the device data from the API."""
        await super().refresh()
        self.update_data({
            "realInfo": await self.api.device_real_info(self.serial)
        })

    # Properties for Sensors
    @property
    def online(self) -> bool:
        """Return the online status of the fountain."""
        return bool(self._data.get("online", False))

    @property
    def battery_state(self) -> str:
        """Get the battery state."""
        return self._data.get("batteryState", "unknown")

    @property
    def wifi_rssi(self) -> int:
        """Get the Wi-Fi signal strength."""
        return self._data.get("wifiRssi", -100)

    @property
    def weight(self) -> float:
        """Get the current weight of the water (in grams)."""
        return self._data.get("weight", 0.0)

    @property
    def weight_percent(self) -> int:
        """Get the current weight percentage of water."""
        return self._data.get("weightPercent", 0)

    @property
    def remaining_filter_days(self) -> int:
        """Get the number of days remaining for the filter replacement."""
        return self._data.get("remainingReplacementDays", 0)

    @property
    def remaining_cleaning_days(self) -> int:
        """Get the number of days remaining for machine cleaning."""
        return self._data.get("remainingCleaningDays", 0)

    # Properties for Binary Sensors
    @property
    def vacuum_state(self) -> bool:
        """Check if the vacuum state is active."""
        return self._data.get("vacuumState", False)

    @property
    def pump_air_state(self) -> bool:
        """Check if the air pump is active."""
        return self._data.get("pumpAirState", False)

    @property
    def barn_door_error(self) -> bool:
        """Check if there's a barn door error."""
        return self._data.get("barnDoorError", False)

    @property
    def running_state(self) -> str:
        """Get the current running state of the device."""
        return self._data.get("runningState", "unknown")

    # Properties for Switches
    @property
    def light_switch(self) -> bool:
        """Check if the light is enabled."""
        return self._data.get("lightSwitch", False)

    @property
    def sound_switch(self) -> bool:
        """Check if the sound is enabled."""
        return self._data.get("soundSwitch", False)

    # Properties for Buttons
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

    # Additional properties from API
    @property
    def today_total_ml(self) -> int:
        """Get the total milliliters of water used today."""
        return self._data.get("todayTotalMl", 0)

    @property
    def use_water_interval(self) -> int:
        """Get the water usage interval."""
        return self._data.get("useWaterInterval", 0)

    @property
    def use_water_duration(self) -> int:
        """Get the water usage duration."""
        return self._data.get("useWaterDuration", 0)

    @property
    def filter_replacement_frequency(self) -> int:
        """Get the filter replacement frequency."""
        return self._data.get("filterReplacementFrequency", 0)

    @property
    def machine_cleaning_frequency(self) -> int:
        """Get the machine cleaning frequency."""
        return self._data.get("machineCleaningFrequency", 0)
