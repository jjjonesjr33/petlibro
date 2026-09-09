from logging import getLogger

from .granary_smart_camera_feeder import GranarySmartCameraFeeder

_LOGGER = getLogger(__name__)


class Granary2VisionFeeder(GranarySmartCameraFeeder):
    """Represents the Granary 2 Vision feeder.

    Temporary subclass of GranarySmartCameraFeeder so the device loads and
    reuses its entities while we confirm real API field names against a
    live Granary 2 Vision unit. Split into a standalone class once verified.
    """

    @property
    def night_vision(self) -> str:
        """Return the current night vision mode.

        Unlike the Granary Smart Camera Feeder, this device reports night
        vision under getAttributeSetting.nightVisionMode; realInfo.nightVision
        is always null.
        """
        return self._data.get("getAttributeSetting", {}).get("nightVisionMode", "unknown")

    @property
    def left_food_low(self) -> bool | None:
        """Return True if the left grain warehouse is low, or None if this unit doesn't report it."""
        value = self._data.get("realInfo", {}).get("leftWarehouseSurplusGrain")
        if value is None:
            return None
        return not bool(value)

    @property
    def right_food_low(self) -> bool | None:
        """Return True if the right grain warehouse is low, or None if this unit doesn't report it."""
        value = self._data.get("realInfo", {}).get("rightWarehouseSurplusGrain")
        if value is None:
            return None
        return not bool(value)

    @property
    def pet_detection_enabled(self) -> bool:
        """Return whether AI pet detection is enabled."""
        return bool(self._data.get("getAttributeSetting", {}).get("petDetectionSwitch", False))

    @property
    def human_detection_enabled(self) -> bool:
        """Return whether AI human detection is enabled."""
        return bool(self._data.get("realInfo", {}).get("enableHumanDetection", False))

    @property
    def talk_channel_active(self) -> bool:
        """Return whether a 2-way talk session is currently active."""
        return bool(self._data.get("realInfo", {}).get("talkChannelState", False))

    @property
    def radar_sensing_level(self) -> str:
        """Return the current radar sensing/trigger level."""
        return self._data.get("realInfo", {}).get("radarSensingLevel", "unknown")

    @property
    def smart_refill_enabled(self) -> bool:
        """Return whether Smart Refill Mode's auto-stop is enabled."""
        return bool(self._data.get("getAttributeSetting", {}).get("autoStopFeedSwitch", False))

    @property
    def smart_refill_max_weight(self) -> float:
        """Return the Smart Refill Mode daily max amount, in grams."""
        value = self._data.get("getAttributeSetting", {}).get("autoFeedMaxWeight")
        return float(value) if isinstance(value, (int, float)) else 0.0
