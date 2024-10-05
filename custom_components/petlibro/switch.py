"""Support for PETLIBRO switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Generic

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PetLibroHubConfigEntry
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription
from .devices.device import Device
from .devices.feeders.feeder import Feeder
from .devices.feeders.one_rfid_smart_feeder import OneRFIDSmartFeeder


@dataclass(frozen=True)
class RequiredKeysMixin(Generic[_DeviceT]):
    """A class that describes devices switch entity required keys."""

    set_fn: Callable[[_DeviceT, bool], Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class PetLibroSwitchEntityDescription(SwitchEntityDescription, PetLibroEntityDescription[_DeviceT], RequiredKeysMixin[_DeviceT]):
    """A class that describes device switch entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG


DEVICE_SWITCH_MAP: dict[type[Device], list[PetLibroSwitchEntityDescription]] = {
    Feeder: [
        PetLibroSwitchEntityDescription[Feeder](
            key="feeding_plan_today_all",
            translation_key="feeding_plan_today_all",
            set_fn=lambda device, value: device.set_feeding_plan_today_all(value),
            name="Today's Feeding Plan (All)"
        )
    ],
    OneRFIDSmartFeeder: [
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="child_lock_switch",
            translation_key="child_lock_switch",
            set_fn=lambda device, value: device.set_child_lock(value),
            name="Child Lock"
        ),
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="enable_light",
            translation_key="enable_light",
            set_fn=lambda device, value: device.set_light_enable(value),
            name="Enable Display"
        ),
        PetLibroSwitchEntityDescription[OneRFIDSmartFeeder](
            key="enable_sound",
            translation_key="enable_sound",
            set_fn=lambda device, value: device.set_sound_enable(value),
            name="Enable Sound"
        )
    ]
}


class PetLibroSwitchEntity(PetLibroEntity[_DeviceT], SwitchEntity):
    """PETLIBRO switch entity."""

    entity_description: PetLibroSwitchEntityDescription[_DeviceT]  # type: ignore [reportIncompatibleVariableOverride]

    @cached_property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return bool(getattr(self.device, self.entity_description.key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.device, False)

async def async_setup_entry(
    _: HomeAssistant,
    entry: PetLibroHubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO switches using config entry."""
    hub = entry.runtime_data
    entities = [
        PetLibroSwitchEntity(device, hub, description)
        for device in hub.devices
        for device_type, entity_descriptions in DEVICE_SWITCH_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]
    async_add_entities(entities)
