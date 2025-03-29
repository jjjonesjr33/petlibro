"""Generic PETLIBRO feeder"""
import logging
from typing import Optional, cast, Any
from ..device import Device


UNITS = {
    1: "cup",
    2: "oz",
    3: "g",
    4: "mL"
}

UNITS_RATIO = {
    1: 1/12,
    2: 0.35,
    3: 10,
    4: 20
}

_LOGGER = logging.getLogger(__name__)

class Feeder(Device):
    """Generic PETLIBRO feeder device"""

    async def refresh(self):
        await super().refresh()
        try:
            feeding_plan_today = await self.api.device_feeding_plan_today_new(self.serial)
            self.update_data({
                "feedingPlanTodayNew": feeding_plan_today
            })
        except Exception as e:
            _LOGGER.warning("Failed to get feeding plan today for %s: %s", self.serial, e)
            # Continue without this data, as it may be available from cache

    @property
    def unit_id(self) -> int | None:
        """The device unit type identifier"""
        return self._data.get("unitType")

    @property
    def unit_type(self) -> str | None:
        """The device unit type"""
        unit : Optional[str] = None

        if unit_id := self.unit_id:
            unit = UNITS.get(unit_id)

        return unit

    @property
    def feeding_plan(self) -> bool:
        return self._data.get("enableFeedingPlan", False)

    async def set_feeding_plan(self, value: bool):
        """Set the feeding plan state."""
        await self.execute_command("feeding_plan", value=value)
        
        # Register activity for adaptive polling
        self._register_activity("set_feeding_plan")
        await self.refresh()
        return True

    @property
    def feeding_plan_today_all(self) -> bool:
        return not cast(bool, self._data.get("feedingPlanTodayNew", {}).get("allSkipped"))

    async def set_feeding_plan_today_all(self, value: bool):
        """Set the feeding plan status for today."""
        await self.execute_command("feeding_plan_today_all", value=value)
        
        # Register activity for adaptive polling
        self._register_activity("set_feeding_plan_today_all")
        await self.refresh()
        return True

    async def set_manual_feed(self):
        """Trigger manual feeding."""
        await self.execute_command("manual_feed")
        
        # Register activity for adaptive polling
        self._register_activity("manual_feed")
        await self.refresh()
        return True

    def convert_unit(self, value: int) -> int:
        """Convert a value to the device unit.

        Args:
            value: Value to convert
            
        Returns:
            Converted value or unchanged if no unit
        """
        if self.unit_id:
            return int(value * UNITS_RATIO.get(self.unit_id, 1))
        return value

    def _register_activity(self, action: str):
        """Register device activity for adaptive polling.
        
        Args:
            action: The action that was performed
        """
        if hasattr(self.hub, "register_device_activity"):
            self.hub.register_device_activity(self.serial, action)
