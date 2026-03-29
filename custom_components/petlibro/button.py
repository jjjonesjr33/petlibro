"""Support for PETLIBRO buttons."""
from __future__ import annotations
import re
from .api import make_api_call
import aiohttp
from aiohttp import ClientSession, ClientError
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic
from logging import getLogger
from .const import DOMAIN
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from .hub import PetLibroHub

_LOGGER = getLogger(__name__)

from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription
from .devices import Device
from .devices.device import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.air_smart_feeder import AirSmartFeeder
from .devices.feeders.granary_smart_feeder import GranarySmartFeeder
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder
from .devices.feeders.polar_wet_food_feeder import PolarWetFoodFeeder
from .devices.feeders.space_smart_feeder import SpaceSmartFeeder
from .devices.fountains.dockstream_smart_fountain import DockstreamSmartFountain
from .devices.fountains.dockstream_smart_rfid_fountain import DockstreamSmartRFIDFountain
from .devices.fountains.dockstream_2_smart_cordless_fountain import Dockstream2SmartCordlessFountain
from .devices.fountains.dockstream_2_smart_fountain import Dockstream2SmartFountain
from .devices.litterboxes.luma_smart_litter_box import LumaSmartLitterBox


@dataclass(frozen=True)
class RequiredKeysMixin(Generic[_DeviceT]):
    """A class that describes devices button entity required keys."""
    set_fn: Callable[[_DeviceT], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class PetLibroButtonEntityDescription(ButtonEntityDescription, PetLibroEntityDescription[_DeviceT], RequiredKeysMixin[_DeviceT]):
    """A class that describes device button entities."""
    entity_category: EntityCategory = EntityCategory.CONFIG
    # For feeding plan buttons: read plan_id from this select entity unique_id suffix
    select_key: str | None = None
    # Async callable(device, plan_id) — used when select_key is set
    plan_fn: Callable | None = None


DEVICE_BUTTON_MAP: dict[type[Device], list[PetLibroButtonEntityDescription]] = {
    Feeder: [
    ],
    AirSmartFeeder: [
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Plan"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_enable",
            translation_key="feeding_plan_enable",
            icon="mdi:calendar-check",
            name="Enable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": True},
            ),
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_disable",
            translation_key="feeding_plan_disable",
            icon="mdi:calendar-remove",
            name="Disable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": False},
            ),
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_delete",
            translation_key="feeding_plan_delete",
            icon="mdi:calendar-minus",
            name="Delete Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_delete(d.serial, pid),
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_skip_today",
            translation_key="feeding_plan_skip_today",
            icon="mdi:calendar-today",
            name="Skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=True),
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_unskip_today",
            translation_key="feeding_plan_unskip_today",
            icon="mdi:calendar-today",
            name="Un-skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=False),
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_today_enable_all",
            translation_key="feeding_plan_today_enable_all",
            icon="mdi:calendar-check",
            name="Enable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, True),
        ),
        PetLibroButtonEntityDescription[AirSmartFeeder](
            key="feeding_plan_today_disable_all",
            translation_key="feeding_plan_today_disable_all",
            icon="mdi:calendar-remove",
            name="Disable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, False),
        ),
    ],
    GranarySmartFeeder: [
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="desiccant_reset",
            translation_key="desiccant_reset",
            set_fn=lambda device: device.set_desiccant_reset(),
            name="Desiccant Replaced"
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_enable",
            translation_key="feeding_plan_enable",
            icon="mdi:calendar-check",
            name="Enable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": True},
            ),
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_disable",
            translation_key="feeding_plan_disable",
            icon="mdi:calendar-remove",
            name="Disable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": False},
            ),
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_delete",
            translation_key="feeding_plan_delete",
            icon="mdi:calendar-minus",
            name="Delete Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_delete(d.serial, pid),
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_skip_today",
            translation_key="feeding_plan_skip_today",
            icon="mdi:calendar-today",
            name="Skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=True),
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_unskip_today",
            translation_key="feeding_plan_unskip_today",
            icon="mdi:calendar-today",
            name="Un-skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=False),
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_today_enable_all",
            translation_key="feeding_plan_today_enable_all",
            icon="mdi:calendar-check",
            name="Enable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, True),
        ),
        PetLibroButtonEntityDescription[GranarySmartFeeder](
            key="feeding_plan_today_disable_all",
            translation_key="feeding_plan_today_disable_all",
            icon="mdi:calendar-remove",
            name="Disable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, False),
        ),
    ],
    GranarySmartCameraFeeder: [
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="desiccant_reset",
            translation_key="desiccant_reset",
            set_fn=lambda device: device.set_desiccant_reset(),
            name="Desiccant Replaced"
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_enable",
            translation_key="feeding_plan_enable",
            icon="mdi:calendar-check",
            name="Enable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": True},
            ),
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_disable",
            translation_key="feeding_plan_disable",
            icon="mdi:calendar-remove",
            name="Disable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": False},
            ),
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_delete",
            translation_key="feeding_plan_delete",
            icon="mdi:calendar-minus",
            name="Delete Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_delete(d.serial, pid),
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_skip_today",
            translation_key="feeding_plan_skip_today",
            icon="mdi:calendar-today",
            name="Skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=True),
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_unskip_today",
            translation_key="feeding_plan_unskip_today",
            icon="mdi:calendar-today",
            name="Un-skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=False),
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_today_enable_all",
            translation_key="feeding_plan_today_enable_all",
            icon="mdi:calendar-check",
            name="Enable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, True),
        ),
        PetLibroButtonEntityDescription[GranarySmartCameraFeeder](
            key="feeding_plan_today_disable_all",
            translation_key="feeding_plan_today_disable_all",
            icon="mdi:calendar-remove",
            name="Disable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, False),
        ),
    ],
    OneRFIDSmartFeeder: [
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="manual_lid_open",
            translation_key="manual_lid_open",
            set_fn=lambda device: device.set_manual_lid_open(),
            name="Manually Open Lid"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="display_on",
            translation_key="display_on",
            set_fn=lambda device: device.set_display_on(),
            name="Turn On Display"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="display_off",
            translation_key="display_off",
            set_fn=lambda device: device.set_display_off(),
            name="Turn Off Display"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="sound_on",
            translation_key="sound_on",
            set_fn=lambda device: device.set_sound_on(),
            name="Turn On Sound"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="sound_off",
            translation_key="sound_off",
            set_fn=lambda device: device.set_sound_off(),
            name="Turn Off Sound"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="desiccant_reset",
            translation_key="desiccant_reset",
            set_fn=lambda device: device.set_desiccant_reset(),
            name="Desiccant Reset"
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_enable",
            translation_key="feeding_plan_enable",
            icon="mdi:calendar-check",
            name="Enable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": True},
            ),
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_disable",
            translation_key="feeding_plan_disable",
            icon="mdi:calendar-remove",
            name="Disable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": False},
            ),
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_delete",
            translation_key="feeding_plan_delete",
            icon="mdi:calendar-minus",
            name="Delete Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_delete(d.serial, pid),
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_skip_today",
            translation_key="feeding_plan_skip_today",
            icon="mdi:calendar-today",
            name="Skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=True),
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_unskip_today",
            translation_key="feeding_plan_unskip_today",
            icon="mdi:calendar-today",
            name="Un-skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=False),
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_today_enable_all",
            translation_key="feeding_plan_today_enable_all",
            icon="mdi:calendar-check",
            name="Enable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, True),
        ),
        PetLibroButtonEntityDescription[OneRFIDSmartFeeder](
            key="feeding_plan_today_disable_all",
            translation_key="feeding_plan_today_disable_all",
            icon="mdi:calendar-remove",
            name="Disable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, False),
        ),
    ],
    PolarWetFoodFeeder: [
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="ring_bell",
            translation_key="ring_bell",
            set_fn=lambda device: device.feed_audio(),
            name="Ring Bell"
        ),
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="rotate_food_bowl",
            translation_key="rotate_food_bowl",
            set_fn=lambda device: device.rotate_food_bowl(),
            name="Rotate Food Bowl"
        ),
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="reposition_schedule",
            translation_key="reposition_schedule",
            set_fn=lambda device: device.reposition_schedule(),
            name="Reposition the schedule"
        ),
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[PolarWetFoodFeeder](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
    ],
    SpaceSmartFeeder: [
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="manual_feed",
            translation_key="manual_feed",
            set_fn=lambda device: device.set_manual_feed(),
            name="Manual Feed"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="enable_feeding_plan",
            translation_key="enable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(True),
            name="Enable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="disable_feeding_plan",
            translation_key="disable_feeding_plan",
            set_fn=lambda device: device.set_feeding_plan(False),
            name="Disable Feeding Schedule"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="sound_on",
            translation_key="sound_on",
            set_fn=lambda device: device.set_sound_on(),
            name="Turn On Sound"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="sound_off",
            translation_key="sound_off",
            set_fn=lambda device: device.set_sound_off(),
            name="Turn Off Sound"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="sleep_on",
            translation_key="sleep_on",
            set_fn=lambda device: device.set_sleep_on(),
            name="Turn On Sleep Mode"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="sleep_off",
            translation_key="sleep_off",
            set_fn=lambda device: device.set_sleep_off(),
            name="Turn Off Sleep Mode"
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_enable",
            translation_key="feeding_plan_enable",
            icon="mdi:calendar-check",
            name="Enable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": True},
            ),
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_disable",
            translation_key="feeding_plan_disable",
            icon="mdi:calendar-remove",
            name="Disable Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_toggle(
                d.serial,
                {**d.feeding_plan_data.get(str(pid), {}), "id": pid, "enable": False},
            ),
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_delete",
            translation_key="feeding_plan_delete",
            icon="mdi:calendar-minus",
            name="Delete Selected Plan",
            set_fn=lambda _: None,
            select_key="feeding_plan_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_delete(d.serial, pid),
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_skip_today",
            translation_key="feeding_plan_skip_today",
            icon="mdi:calendar-today",
            name="Skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=True),
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_unskip_today",
            translation_key="feeding_plan_unskip_today",
            icon="mdi:calendar-today",
            name="Un-skip Selected Plan Today",
            set_fn=lambda _: None,
            select_key="feeding_plan_today_select",
            plan_fn=lambda d, pid: d.api.feeding_plan_today_skip(d.serial, pid, skip=False),
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_today_enable_all",
            translation_key="feeding_plan_today_enable_all",
            icon="mdi:calendar-check",
            name="Enable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, True),
        ),
        PetLibroButtonEntityDescription[SpaceSmartFeeder](
            key="feeding_plan_today_disable_all",
            translation_key="feeding_plan_today_disable_all",
            icon="mdi:calendar-remove",
            name="Disable Today's Feeding Schedule",
            set_fn=lambda d: d.api.feeding_plan_today_all(d.serial, False),
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroButtonEntityDescription[DockstreamSmartFountain](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[DockstreamSmartFountain](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[DockstreamSmartFountain](
            key="cleaning_reset",
            translation_key="cleaning_reset",
            set_fn=lambda device: device.set_cleaning_reset(),
            name="Cleaning Reset"
        ),
        PetLibroButtonEntityDescription[DockstreamSmartFountain](
            key="filter_reset",
            translation_key="filter_reset",
            set_fn=lambda device: device.set_filter_reset(),
            name="Filter Reset"
        )
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroButtonEntityDescription[DockstreamSmartRFIDFountain](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[DockstreamSmartRFIDFountain](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[DockstreamSmartRFIDFountain](
            key="cleaning_reset",
            translation_key="cleaning_reset",
            set_fn=lambda device: device.set_cleaning_reset(),
            name="Cleaning Reset"
        ),
        PetLibroButtonEntityDescription[DockstreamSmartRFIDFountain](
            key="filter_reset",
            translation_key="filter_reset",
            set_fn=lambda device: device.set_filter_reset(),
            name="Filter Reset"
        )
    ],
    Dockstream2SmartCordlessFountain: [
        PetLibroButtonEntityDescription[Dockstream2SmartCordlessFountain](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[Dockstream2SmartCordlessFountain](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[Dockstream2SmartCordlessFountain](
            key="cleaning_reset",
            translation_key="cleaning_reset",
            set_fn=lambda device: device.set_cleaning_reset(),
            name="Cleaning Reset"
        ),
        PetLibroButtonEntityDescription[Dockstream2SmartCordlessFountain](
            key="filter_reset",
            translation_key="filter_reset",
            set_fn=lambda device: device.set_filter_reset(),
            name="Filter Reset"
        )
    ],
    Dockstream2SmartFountain: [
        PetLibroButtonEntityDescription[Dockstream2SmartFountain](
            key="light_on",
            translation_key="light_on",
            set_fn=lambda device: device.set_light_on(),
            name="Turn On Indicator"
        ),
        PetLibroButtonEntityDescription[Dockstream2SmartFountain](
            key="light_off",
            translation_key="light_off",
            set_fn=lambda device: device.set_light_off(),
            name="Turn Off Indicator"
        ),
        PetLibroButtonEntityDescription[Dockstream2SmartFountain](
            key="cleaning_reset",
            translation_key="cleaning_reset",
            set_fn=lambda device: device.set_cleaning_reset(),
            name="Cleaning Reset"
        ),
        PetLibroButtonEntityDescription[Dockstream2SmartFountain](
            key="filter_reset",
            translation_key="filter_reset",
            set_fn=lambda device: device.set_filter_reset(),
            name="Filter Reset"
        )
    ],
    LumaSmartLitterBox: [
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_clean",
            translation_key="trigger_clean",
            set_fn=lambda device: device.trigger_manual_clean(),
            name="Start Clean Cycle",
        ),
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_empty_waste",
            translation_key="trigger_empty_waste",
            set_fn=lambda device: device.trigger_empty_waste(),
            name="Empty Waste Bin",
        ),
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_level_litter",
            translation_key="trigger_level_litter",
            set_fn=lambda device: device.trigger_level_litter(),
            name="Level Litter",
        ),
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_stop_action",
            translation_key="trigger_stop_action",
            set_fn=lambda device: device.trigger_stop_action(),
            name="Stop Current Action",
        ),
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_open_door",
            translation_key="trigger_open_door",
            set_fn=lambda device: device.trigger_open_door(),
            name="Open Door",
        ),
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_close_door",
            translation_key="trigger_close_door",
            set_fn=lambda device: device.trigger_close_door(),
            name="Close Door",
        ),
        PetLibroButtonEntityDescription[LumaSmartLitterBox](
            key="trigger_vacuum",
            translation_key="trigger_vacuum",
            set_fn=lambda device: device.trigger_vacuum(),
            name="Run Air Purifier",
        ),
    ],
}


class PetLibroButtonEntity(PetLibroEntity[_DeviceT], ButtonEntity):
    """PETLIBRO button entity."""
    entity_description: PetLibroButtonEntityDescription[_DeviceT]

    @property
    def available(self) -> bool:
        """Check if the device is available."""
        return getattr(self.device, 'online', False)

    def _get_plan_id(self, select_key: str) -> int:
        """Read the currently selected plan ID from the companion select entity."""
        ent_reg = er.async_get(self.hass)
        unique_id = f"{self.device.serial}-{select_key}"
        entity_id = ent_reg.async_get_entity_id("select", DOMAIN, unique_id)

        if not entity_id:
            raise HomeAssistantError(
                f"No feeding plan selector found for {self.device.name}. "
                "Make sure the integration has loaded correctly."
            )

        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable", "No plans", "No plans today"):
            raise HomeAssistantError(
                f"No plan selected on {self.device.name}. "
                "Select a plan from the feeding plan dropdown first."
            )

        match = re.search(r"-\s*(\d+)\s*$", state.state)
        if not match:
            raise HomeAssistantError(
                f"Could not extract a plan ID from '{state.state}'."
            )

        return int(match.group(1))

    async def async_press(self) -> None:
        """Handle the button press."""
        desc = self.entity_description
        _LOGGER.debug("Pressing button: %s for device %s", desc.name, self.device.name)

        try:
            if desc.select_key and desc.plan_fn:
                # Plan-specific button: read selected plan from select entity
                plan_id = self._get_plan_id(desc.select_key)
                await desc.plan_fn(self.device, plan_id)
                _LOGGER.debug(
                    "Button '%s' pressed for plan %d on %s",
                    desc.name, plan_id, self.device.name,
                )
            else:
                # Standard button
                await desc.set_fn(self.device)
                _LOGGER.debug("Successfully pressed button: %s", desc.name)

            await self.device.refresh()

        except HomeAssistantError:
            raise
        except Exception as e:
            _LOGGER.error(
                "Error pressing button %s for device %s: %s",
                desc.name, self.device.name, e,
                exc_info=True,
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO buttons using config entry."""
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    if not hub.devices:
        _LOGGER.warning("No devices found in hub during button setup.")
        return

    _LOGGER.debug("Hub data: %s", hub)
    devices = hub.devices
    _LOGGER.debug("Devices in hub: %s", devices)

    entities = [
        PetLibroButtonEntity(device, hub, description)
        for device in devices.values()
        for device_type, entity_descriptions in DEVICE_BUTTON_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No buttons added, entities list is empty!")
    else:
        _LOGGER.debug("Adding %d PetLibro buttons", len(entities))
        for entity in entities:
            _LOGGER.debug(
                "Adding button entity: %s for device %s",
                entity.entity_description.name,
                entity.device.name,
            )
        async_add_entities(entities)