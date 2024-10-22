from .feeder import BaseFeeder


class OneRFIDSmartFeeder(BaseFeeder):
    @property
    def today_eating_times(self) -> int:
        return self._data.get("grainStatus", {}).get("todayEatingTimes", 0)

    @property
    def today_eating_time(self) -> int:
        eating_time_str = self._data.get("grainStatus", {}).get("eatingTime", "0'0''")
        if not eating_time_str:
            return 0
        try:
            minutes, seconds = map(int, eating_time_str.replace("''", "").split("'"))
            total_seconds = minutes * 60 + seconds
        except ValueError:
            return 0
        return total_seconds

    @property
    def door_state(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("barnDoorState", False))

    @property
    def door_blocked(self) -> bool:
        return bool(self._data.get("realInfo", {}).get("barnDoorError", False))
