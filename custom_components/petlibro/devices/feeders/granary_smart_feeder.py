from typing import cast
from logging import getLogger
from ..device import Device
from .feeder import Feeder

_LOGGER = getLogger(__name__)

class GranarySmartFeeder(Device):  # Inherit directly from Device
    async def refresh(self):
        """Refresh the device data from the API."""
        await super().refresh()  # Call the refresh method from Device
        
        # Fetch grain status and update data
        grain_status = await self.api.device_grain_status(self.serial)
        self.update_data({
            "grainStatus": grain_status or {}
        })

    @property
    def remaining_desiccant(self) -> str:
        """Get the remaining desiccant days."""
        return cast(str, self._data.get("remainingDesiccantDays", "unknown"))

    @property
    def today_feeding_quantity(self) -> int:
        """Get the feeding quantity for today, converted to the correct unit."""
        quantity = self._data.get("grainStatus", {}).get("todayFeedingQuantity", 0)
        return self.convert_unit(quantity)

    @property
    def today_feeding_times(self) -> int:
        """Get the number of feeding times for today."""
        return cast(int, self._data.get("grainStatus", {}).get("todayFeedingTimes", 0))

    def convert_unit(self, value: int) -> int:
        """Convert the feeding quantity to the desired unit (e.g., cups)."""
        # Assuming the value is in milliliters, and we want to convert it to cups
        return round(value / 236.588)
