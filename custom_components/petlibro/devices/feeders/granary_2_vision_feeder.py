import aiohttp
from logging import getLogger

from ...exceptions import PetLibroAPIError
from .granary_smart_camera_feeder import GranarySmartCameraFeeder

_LOGGER = getLogger(__name__)


class Granary2VisionFeeder(GranarySmartCameraFeeder):
    """Represents the Granary 2 Vision feeder.

    Temporary subclass of GranarySmartCameraFeeder so the device loads and
    reuses its entities while we confirm real API field names against a
    live Granary 2 Vision unit. Split into a standalone class once verified.
    """

    async def refresh(self):
        """Refresh the device data from the API."""
        await super().refresh()
        try:
            free_feeding_setting = await self.api.device_get_free_feeding_setting(self.serial)
            self.update_data({
                "freeFeedingSetting": free_feeding_setting or {},
            })
        except PetLibroAPIError as err:
            _LOGGER.error(f"Error refreshing free feeding setting for Granary2VisionFeeder: {err}")

        # Isolated in its own error handler: TUTK credential retrieval failing
        # (e.g. no camera entitlement) shouldn't disrupt the rest of the refresh.
        try:
            tutk_info = await self.api.device_tutk_info(self.serial)
            self.update_data({
                "tutkInfo": tutk_info or {},
            })
        except PetLibroAPIError as err:
            _LOGGER.error(f"Error refreshing TUTK camera info for Granary2VisionFeeder: {err}")

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
    def free_feeding_per_grain(self) -> float | None:
        """Return the amount dispensed per Free Feeding (Smart Feed) top-up."""
        value = self._data.get("freeFeedingSetting", {}).get("freePerGrainNum")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def free_feeding_daily_max(self) -> float | None:
        """Return the max number of Free Feeding top-ups allowed per day."""
        value = self._data.get("freeFeedingSetting", {}).get("freeDailyMaxNum")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def free_feeding_leftover_weight(self) -> float | None:
        """Return the minimum food-left threshold that pauses Free Feeding."""
        value = self._data.get("freeFeedingSetting", {}).get("freeLeftoverWeight")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def free_feeding_wait_seconds(self) -> float | None:
        """Return the wait time (seconds) Free Feeding uses between checks."""
        value = self._data.get("freeFeedingSetting", {}).get("freeWaitSeconds")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def camera_id(self) -> str | None:
        """Return the Kalay/TUTK camera UID, if this device has camera entitlement."""
        return self._data.get("tutkInfo", {}).get("cameraId")

    @property
    def camera_auth_info(self) -> str | None:
        """Return the Kalay/TUTK camera auth info string."""
        value = self._data.get("tutkInfo", {}).get("cameraAuthInfo")
        return value if value is not None else self._data.get("realInfo", {}).get("cameraAuthInfo")

    @property
    def tutk_user_token(self) -> str | None:
        """Return the Kalay/TUTK user token used to establish a P2P session."""
        return self._data.get("tutkInfo", {}).get("userToken")

    @property
    def tutk_app_url(self) -> str | None:
        """Return the Kalay/TUTK app URL/endpoint for this account."""
        return self._data.get("tutkInfo", {}).get("appUrl")

    async def set_free_feeding_mode(self) -> None:
        """Enable Free Feeding (Smart Feed) mode."""
        _LOGGER.debug(f"Enabling Free Feeding mode for {self.serial}")
        try:
            await self.api.set_feeding_mode(self.serial, "FREE")
            await self.refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to enable Free Feeding mode for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error enabling Free Feeding mode: {err}")

    async def set_plan_feeding_mode(self) -> None:
        """Switch back to schedule-based (Feeding Plan) mode."""
        _LOGGER.debug(f"Enabling Plan feeding mode for {self.serial}")
        try:
            await self.api.set_feeding_mode(self.serial, "PLAN")
            await self.refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to enable Plan feeding mode for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error enabling Plan feeding mode: {err}")
