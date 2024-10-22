from .feeder import BaseFeeder


class GranarySmartCameraFeeder(BaseFeeder):
    @property
    def resolution(self) -> str:
        """Return the camera resolution."""
        return self._data.get("realInfo", {}).get("resolution", "unknown")

    @property
    def night_vision(self) -> str:
        """Return the current night vision mode."""
        return self._data.get("realInfo", {}).get("nightVision", "unknown")

    @property
    def enable_video_record(self) -> bool:
        """Return whether video recording is enabled."""
        return self._data.get("realInfo", {}).get("enableVideoRecord", False)

    @property
    def video_record_switch(self) -> bool:
        """Return the state of the video recording switch."""
        return self._data.get("realInfo", {}).get("videoRecordSwitch", False)

    @property
    def video_record_mode(self) -> str:
        """Return the current video recording mode."""
        return self._data.get("realInfo", {}).get("videoRecordMode", "unknown")
