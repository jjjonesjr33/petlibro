from ..device import Device

class DockstreamSmartRFIDFountain(Device):
    """Represents the Dockstream Smart RFID Fountain device."""

    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            data = await self.api.device_real_info(self.serial)  # Assuming device_real_info gives relevant data
            self.update_data(data)
        except Exception as e:
            _LOGGER.error(f"Failed to refresh Dockstream Smart RFID Fountain data: {e}")

    @property
    def extra_state_attributes(self) -> dict:
        """Return all available data as attributes."""
        return self._data

    @property
    def water_level(self) -> str:
        """Get the water level of the fountain."""
        return self._data.get("waterLevel", "unknown")

    @property
    def filter_status(self) -> str:
        """Get the filter status of the fountain."""
        return self._data.get("filterStatus", "unknown")

    @property
    def online(self) -> bool:
        """Return if the device is online."""
        return bool(self._data.get("online", False))

    @property
    def remaining_filter_days(self) -> int:
        """Return the remaining days before the filter needs to be replaced."""
        return self._data.get("remainingFilterDays", 0)

    @property
    def pump_state(self) -> bool:
        """Return the state of the pump (True for running, False for off)."""
        return bool(self._data.get("pumpState", False))

    @property
    def enable_low_water_notice(self) -> bool:
        """Return if low water notifications are enabled."""
        return bool(self._data.get("enableLowWaterNotice", False))

