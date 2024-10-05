from ..device import Device

class DockstreamSmartRFIDFountain(Device):
    """Represents the Dockstream Smart RFID Fountain device."""

    @property
    def water_level(self) -> str:
        """Get the water level of the fountain."""
        return self._data.get("waterLevel", "unknown")

    @property
    def filter_status(self) -> str:
        """Get the filter status of the fountain."""
        return self._data.get("filterStatus", "unknown")

    # You can add more properties and methods here specific to the fountain
