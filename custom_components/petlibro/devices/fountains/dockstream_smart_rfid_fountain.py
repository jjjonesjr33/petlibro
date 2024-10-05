from ..device import Device

class DockstreamSmartRFIDFountain(Device):
    """Represents the Dockstream Smart RFID Fountain device."""

    @property
    def extra_state_attributes(self) -> dict:
        """Return all available data as attributes."""
        # Return the raw data received from the API as attributes
        return self._data

    # Optionally, add specific properties if you know certain fields should be present
    @property
    def water_level(self) -> str:
        """Get the water level of the fountain."""
        return self._data.get("waterLevel", "unknown")

    @property
    def filter_status(self) -> str:
        """Get the filter status of the fountain."""
        return self._data.get("filterStatus", "unknown")

    # Any other specific attributes you know can go here
