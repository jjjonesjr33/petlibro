"""PETLIBRO Granary 2 feeder (PLAF105)."""
from __future__ import annotations

from datetime import datetime
from logging import getLogger
from zoneinfo import ZoneInfo

import aiohttp
from homeassistant.util import dt as dt_util

from ...exceptions import PetLibroAPIError
from .granary_smart_feeder import GranarySmartFeeder

_LOGGER = getLogger(__name__)


def _numeric_value(value: object) -> float | None:
    """Return an API number as a float, treating booleans and non-numbers as missing."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class Granary2Feeder(GranarySmartFeeder):
    """The Granary 2 (PLAF105): a Granary feeder with a bowl scale and Free Feeding mode, no camera.

    The cloud reports it with productName "Granary 2". Its bowl-scale and
    feeding-mode fields live on /data/data/realInfo and
    /device/device/getFreeFeedingSetting, the same endpoints the Granary 2
    Vision (PLAF205) uses; the camera layer of that model is absent here, so
    no image or camera entities are created.

    Two things differ from the older Granary feeders (observed on firmware
    1.0.33, 2026-11-01):

    * /device/feedingPlan/todayNew and /device/feedingPlan/list answer with
      empty plans even while a schedule is active, so the next feed is read
      from the nextFeedingDay / nextFeedingTime fields of the device's
      /device/device/list entry, which this class re-reads on every refresh.
    * The Granary base refresh is all-or-nothing: one endpoint this model
      does not answer would drop the whole update. Each call is isolated here.
    """

    async def _fetch(self, label: str, coro, default):
        """Await one API call, returning ``default`` instead of raising."""
        try:
            return await coro
        except (PetLibroAPIError, aiohttp.ClientError) as err:
            _LOGGER.debug("Granary 2 %s: %s unavailable: %s", self.serial, label, err)
            return default

    async def refresh(self):
        """Refresh the device data from the API, one endpoint at a time."""
        self._cached_get_next_feed = None
        # Device.refresh: baseInfo + realInfo + attribute settings + bound pets, merged top-level.
        await super(GranarySmartFeeder, self).refresh()

        api, serial = self.api, self.serial
        grain_status = await self._fetch("grainStatus", api.device_grain_status(serial), {})
        real_info = await self._fetch("realInfo", api.device_real_info(serial), {})
        upgrade = await self._fetch("getUpgrade", api.get_device_upgrade(serial), {})
        attribute_settings = await self._fetch(
            "getAttributeSetting", api.device_attribute_settings(serial), {}
        )
        work_record = await self._fetch("workRecord", api.get_device_work_record(serial), [])
        default_matrix = await self._fetch("getDefaultMatrix", api.get_default_matrix(serial), {})
        plan_today = await self._fetch(
            "feedingPlan/todayNew", api.device_feeding_plan_today_new(serial), {}
        )
        plan_list = (
            await self._fetch("feedingPlan/list", api.device_feeding_plan_list(serial), [])
            if self._data.get("enableFeedingPlan")
            else []
        )
        data_real_info = await self._fetch("data/realInfo", api.device_data_real_info(serial), {})
        free_feeding = await self._fetch(
            "getFreeFeedingSetting", api.device_get_free_feeding_setting(serial), {}
        )

        # The list entry is the only place the cloud states this model's next feed.
        list_entry: dict = {}
        for entry in await self._fetch("device/list", api.list_devices(), []) or []:
            if isinstance(entry, dict) and entry.get("deviceSn") == serial:
                list_entry = entry
                break

        self.update_data({
            **list_entry,
            "grainStatus": grain_status or {},
            "realInfo": real_info or {},
            "getUpgrade": upgrade or {},
            "getAttributeSetting": attribute_settings or {},
            "getDefaultMatrix": default_matrix or {},
            "getfeedingplantoday": plan_today or {},
            "feedingPlan": plan_list or [],
            "workRecord": work_record if work_record is not None else [],
            "dataRealInfo": data_real_info if isinstance(data_real_info, dict) else {},
            "freeFeedingSetting": free_feeding if isinstance(free_feeding, dict) else {},
        })

    # ------------------------------------------------------------------ helpers

    @property
    def _scale(self) -> dict:
        """The /data/data/realInfo payload: bowl scale, feeding mode, free-feeding settings."""
        data = self._data.get("dataRealInfo")
        return data if isinstance(data, dict) else {}

    @property
    def _real_info(self) -> dict:
        data = self._data.get("realInfo")
        return data if isinstance(data, dict) else {}

    def _string_field(self, key: str) -> str | None:
        """Read a string field from the scale payload, then realInfo, then the list entry."""
        for source in (self._scale, self._real_info, self._data):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    # ------------------------------------------------------------- bowl scale

    @property
    def bowl_mode(self) -> str | None:
        """Return the configured bowl mode (SINGLE_BOWL on the Granary 2)."""
        return self._string_field("bowlMode")

    @property
    def remaining_food_weight(self) -> float | None:
        """Return the food left in the bowl, in grams, as the bowl scale reads it."""
        return _numeric_value(self._scale.get("remainingGrain"))

    @property
    def remaining_food_portions(self) -> float | None:
        """Return the food left in the bowl, in feeder portions."""
        return _numeric_value(self._scale.get("remainingGrainNum"))

    @property
    def max_feedable(self) -> float | None:
        """Return how many more portions fit in the bowl before the auto-feed maximum."""
        return _numeric_value(self._scale.get("maxFeedable"))

    @property
    def auto_feed_max_weight(self) -> float | None:
        """Return the configured bowl maximum for automatic feeds, in grams."""
        value = self._scale.get("autoFeedMaxWeight")
        if value is None:
            value = self._data.get("autoFeedMaxWeight")
        return _numeric_value(value)

    @property
    def portion_to_gram_ratio(self) -> float | None:
        """Return the number of grams in one feeder portion."""
        return _numeric_value(self._scale.get("portionToGramRatio"))

    @property
    def auto_stop_feed_enabled(self) -> bool | None:
        """Return whether a feed stops once the bowl reaches the auto-feed maximum."""
        for source in (self._scale, self._data):
            value = source.get("autoStopFeedSwitch")
            if isinstance(value, bool):
                return value
        return None

    # ----------------------------------------------------------- feeding mode

    @property
    def feeding_mode(self) -> str | None:
        """Return the feeding mode: PLAN (schedule) or FREE (Smart Feed by bowl weight)."""
        return self._string_field("feedingMode")

    @property
    def free_feeding_per_grain(self) -> float | None:
        """Return the portions dispensed per Free Feeding top-up."""
        return self._free_feeding_value("freePerGrainNum")

    @property
    def free_feeding_daily_max(self) -> float | None:
        """Return the maximum number of Free Feeding top-ups per day."""
        return self._free_feeding_value("freeDailyMaxNum")

    @property
    def free_feeding_leftover_weight(self) -> float | None:
        """Return the bowl weight, in grams, below which Free Feeding tops up."""
        return self._free_feeding_value("freeLeftoverWeight")

    @property
    def free_feeding_wait_seconds(self) -> float | None:
        """Return the wait, in seconds, Free Feeding keeps between top-ups."""
        return self._free_feeding_value("freeWaitSeconds")

    def _free_feeding_value(self, key: str) -> float | None:
        setting = self._data.get("freeFeedingSetting")
        value = setting.get(key) if isinstance(setting, dict) else None
        if value is None:
            value = self._scale.get(key)
        return _numeric_value(value)

    @property
    def meal_call_enabled(self) -> bool | None:
        """Return whether the meal-call sound plays at feeds."""
        attribute_settings = self._data.get("getAttributeSetting")
        for source in (self._scale, attribute_settings if isinstance(attribute_settings, dict) else {}):
            value = source.get("mealCallSwitch")
            if isinstance(value, bool):
                return value
        return None

    # ---------------------------------------------------- hopper, power, care

    @property
    def hopper_state(self) -> str | None:
        """Return the hopper (grain warehouse) level as the cloud words it, e.g. GOOD."""
        return self._string_field("warehouseSurplusGrain")

    @property
    def power_state(self) -> str | None:
        """Return the power state as the cloud words it, e.g. CHARGED."""
        return self._string_field("powerState")

    @property
    def remaining_cleaning_days(self) -> float | None:
        """Return the days left before the next cleaning reminder."""
        for source in (self._scale, self._real_info, self._data):
            value = _numeric_value(source.get("remainingCleaningDays"))
            if value is not None:
                return value
        return None

    @property
    def clean_state(self) -> str | None:
        """Return the cleaning reminder state, e.g. GOOD."""
        return self._string_field("cleanState")

    @property
    def desiccant_state(self) -> str | None:
        """Return the desiccant reminder state, e.g. GOOD."""
        return self._string_field("desiccantState")

    # -------------------------------------------------------------- next feed

    @property
    def next_feed_time(self) -> datetime | None:
        """Return the next scheduled feed as a UTC datetime.

        Uses the feeding plan when the cloud returns one; otherwise the
        nextFeedingDay / nextFeedingTime fields of the device-list entry,
        which are in the device's own time zone.
        """
        from_plan = super().next_feed_time
        if from_plan is not None:
            return from_plan

        day = self._data.get("nextFeedingDay")
        clock = self._data.get("nextFeedingTime")
        if not (isinstance(day, str) and isinstance(clock, str) and ":" in clock):
            return None
        try:
            zone = ZoneInfo(self._data.get("timezone") or "UTC")
            local = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M").replace(tzinfo=zone)
        except (ValueError, KeyError, OSError) as err:
            _LOGGER.debug("Granary 2 %s: unreadable next feed %r %r: %s", self.serial, day, clock, err)
            return None
        return local.astimezone(dt_util.UTC)

    # ---------------------------------------------------------------- actions

    async def set_free_feeding_mode(self) -> None:
        """Switch to Free Feeding (Smart Feed): top up by bowl weight."""
        _LOGGER.debug(f"Enabling Free Feeding mode for {self.serial}")
        try:
            await self.api.set_feeding_mode(self.serial, "FREE")
            await self.refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to enable Free Feeding mode for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error enabling Free Feeding mode: {err}")

    async def set_plan_feeding_mode(self) -> None:
        """Switch back to the feeding plan (schedule)."""
        _LOGGER.debug(f"Enabling Plan feeding mode for {self.serial}")
        try:
            await self.api.set_feeding_mode(self.serial, "PLAN")
            await self.refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to enable Plan feeding mode for {self.serial}: {err}")
            raise PetLibroAPIError(f"Error enabling Plan feeding mode: {err}")
