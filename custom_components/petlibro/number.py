"""Support for PETLIBRO numbers."""
from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable
import logging
from .const import DOMAIN, Unit, APIKey, MANUAL_FEED_PORTIONS
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import UnitOfVolume, Platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry  # Added ConfigEntry import
from homeassistant.util.unit_conversion import VolumeConverter
from .hub import PetLibroHub  # Adjust the import path as necessary


_LOGGER = logging.getLogger(__name__)

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
from .entity import PetLibroEntity, _DeviceT, PetLibroEntityDescription

@dataclass(frozen=True)
class PetLibroNumberEntityDescription(NumberEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """A class that describes device number entities."""
    value_fn: Callable[[_DeviceT], float] = lambda _: 0
    method: Callable[[_DeviceT, float], float] = lambda d, v: None
    petlibro_unit: APIKey | str | None = None

class PetLibroNumberEntity(PetLibroEntity[_DeviceT], NumberEntity):
    """PETLIBRO number entity."""
    entity_description: PetLibroNumberEntityDescription[_DeviceT]

    def __init__(self, device, hub, description):
        """Initialize the number."""
        super().__init__(device, hub, description)

        if (unit_type := self.entity_description.petlibro_unit) and unit_type == APIKey.FEED_UNIT:
            self.hub.manual_feed_unique_ids[Platform.NUMBER].append(self._attr_unique_id)

    @property
    def native_value(self) -> float | None:
        """Return the current state."""
        match self.key:
            case "manual_feed_quantity": 
                return Unit.convert_feed(
                    self.device.manual_feed_quantity * self.device.feed_conv_factor, 
                    None, self.member.feedUnitType, True
                ) if not self.portions_enabled else self.device.manual_feed_quantity
            case "water_low_threshold":
                return Unit.round(
                    VolumeConverter.convert(self.device.water_low_threshold, UnitOfVolume.MILLILITERS, 
                    self.member.waterUnitType.symbol), self.member.waterUnitType
                )
            case _:
                if (value_fn := self.entity_description.value_fn(self.device)) is not None:
                    return value_fn

        state = getattr(self.device, self.key, None)
        if state is None:
            _LOGGER.warning(f"Value '{self.key}' is None for device {self.device.name}")
            return None
        _LOGGER.debug(f"Retrieved value for '{self.key}', {self.device.name}: {state}")
        return float(state)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number."""
        _LOGGER.debug(f"Setting value {value} for {self.device.name}")
        
        try:
            match self.key:
                case "manual_feed_quantity":
                    await self.device.set_manual_feed_quantity(round(Unit.convert_feed(
                        value / self.device.feed_conv_factor, self.member.feedUnitType, None)) 
                        if not self.portions_enabled else round(value))
                case "water_low_threshold":
                    await self.device.set_water_low_threshold(round(VolumeConverter.convert(
                        value, self.member.waterUnitType.symbol, UnitOfVolume.MILLILITERS)))
                case _:
                    # Regular case for sound_level or other methods that only need a value
                    _LOGGER.debug(f"Calling method with value={value} for {self.device.name}")
                    await self.entity_description.method(self.device, value)
                    
            self.async_write_ha_state()
            _LOGGER.debug(f"Value {value} set successfully for {self.device.name}")
        except Exception as e:
            _LOGGER.error(f"Error setting value {value} for {self.device.name}: {e}")

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        match self.key:
            case "manual_feed_quantity": 
                return self.member.feedUnitType.symbol if not self.portions_enabled else "portions",
            case "water_low_threshold": 
                return self.member.waterUnitType.symbol
        return super().native_unit_of_measurement

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        match self.key:
            case "manual_feed_quantity":
                return (self.member.feedUnitType.factor * self.device.feed_conv_factor
                    if not self.portions_enabled else 1)
            case "water_low_threshold": 
                return Unit.round(self.member.waterUnitType.factor * 650, self.member.waterUnitType)
        return super().native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        match self.key:
            case "manual_feed_quantity":
                return (
                    Unit.round((self.member.feedUnitType.factor * self.device.feed_conv_factor)
                        * self.device.max_feed_portions, self.member.feedUnitType,)
                    if not self.portions_enabled else self.device.max_feed_portions)
            case "water_low_threshold":
                return Unit.round(self.member.waterUnitType.factor * 3000, self.member.waterUnitType)
        return super().native_max_value

    @property
    def native_step(self) -> float | None:
        """Return the increment/decrement step."""
        match self.key:
            case "manual_feed_quantity":
                return (self.member.feedUnitType.factor * self.device.feed_conv_factor
                    if not self.portions_enabled else 1)
            case "water_low_threshold":
                return Unit.round(self.member.waterUnitType.factor, self.member.waterUnitType)
        return super().native_step

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.key == "manual_feed_quantity": 
            return self.enable_for_manual_feed
        return super().available

    @property
    def entity_registry_visible_default(self) -> bool:
        """Return if the entity should be visible when first added."""
        if self.key == "manual_feed_quantity": 
            return self.enable_for_manual_feed
        return super().entity_registry_visible_default

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added."""
        if self.key == "manual_feed_quantity": 
            return self.enable_for_manual_feed
        return super().entity_registry_enabled_default

    @property
    def portions_enabled(self) -> bool:
        """Return True if portions are enabled for setting manual feed."""
        return self.hub.entry.options.get(MANUAL_FEED_PORTIONS, False)

    @property
    def enable_for_manual_feed(self) -> bool:
        """Return True if the platform should be enabled for setting manual feed."""
        return self.member.feedUnitType is not Unit.CUPS or self.portions_enabled

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (self.entity_description.petlibro_unit == APIKey.FEED_UNIT
            and self.enabled != self.enable_for_manual_feed
        ):
            self.hub.unit_entities.schedule_manual_feed_sync()
            _LOGGER.warning("Feed unit mismatch, reloading integration.")

        if self.enabled:
            super()._handle_coordinator_update()


DEVICE_NUMBER_MAP: dict[type[Device], list[PetLibroNumberEntityDescription]] = {
    Feeder: [],
    AirSmartFeeder: [
        PetLibroNumberEntityDescription[AirSmartFeeder](
            key="manual_feed_quantity",
            translation_key="manual_feed_quantity",
            name="Manual Feed Quantity",
            icon="mdi:scale",
            mode=NumberMode.SLIDER,
            petlibro_unit=APIKey.FEED_UNIT,
        ),
    ],
    GranarySmartFeeder: [
        PetLibroNumberEntityDescription[GranarySmartFeeder](
            key="manual_feed_quantity",
            translation_key="manual_feed_quantity",
            name="Manual Feed Quantity",
            icon="mdi:scale",
            mode=NumberMode.SLIDER,
            petlibro_unit=APIKey.FEED_UNIT,
        ),
        PetLibroNumberEntityDescription[GranarySmartFeeder](
            key="desiccant_frequency",
            translation_key="desiccant_frequency",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.desiccant_frequency,
            method=lambda device, value: device.set_desiccant_cycle(value),
            name="Desiccant Frequency",
        ),
    ],
    GranarySmartCameraFeeder: [
        PetLibroNumberEntityDescription[GranarySmartCameraFeeder](
            key="manual_feed_quantity",
            translation_key="manual_feed_quantity",
            name="Manual Feed Quantity",
            icon="mdi:scale",
            mode=NumberMode.SLIDER,
            petlibro_unit=APIKey.FEED_UNIT,
        ),
        PetLibroNumberEntityDescription[GranarySmartCameraFeeder](
            key="desiccant_frequency",
            translation_key="desiccant_frequency",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode=NumberMode.BOX,
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.desiccant_frequency,
            method=lambda device, value: device.set_desiccant_cycle(value),
            name="Desiccant Frequency",
        ),
    ],
    OneRFIDSmartFeeder: [
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="desiccant_cycle",
            translation_key="desiccant_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.desiccant_cycle,
            method=lambda device, value: device.set_desiccant_cycle(value),
            name="Desiccant Cycle",
        ),
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="sound_level",
            translation_key="sound_level",
            icon="mdi:volume-high",
            native_unit_of_measurement="%",
            native_max_value=100,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.sound_level,
            method=lambda device, value: device.set_sound_level(value),
            name="Sound Level",
        ),
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="lid_close_time",
            translation_key="lid_close_time",
            icon="mdi:timer",
            native_unit_of_measurement="s",
            native_max_value=10,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.lid_close_time,
            method=lambda device, value: device.set_lid_close_time(value),
            name="Lid Close Time",
        ),
        PetLibroNumberEntityDescription[OneRFIDSmartFeeder](
            key="manual_feed_quantity",
            translation_key="manual_feed_quantity",
            name="Manual Feed Quantity",
            icon="mdi:scale",
            mode=NumberMode.SLIDER,
            petlibro_unit=APIKey.FEED_UNIT,
        ),
    ],
    PolarWetFoodFeeder: [],
    SpaceSmartFeeder: [
        PetLibroNumberEntityDescription[SpaceSmartFeeder](
            key="manual_feed_quantity",
            translation_key="manual_feed_quantity",
            name="Manual Feed Quantity",
            icon="mdi:scale",
            mode=NumberMode.SLIDER,
            petlibro_unit=APIKey.FEED_UNIT,
        ),
        PetLibroNumberEntityDescription[SpaceSmartFeeder](
            key="sound_level",
            translation_key="sound_level",
            icon="mdi:volume-high",
            native_unit_of_measurement="%",
            native_max_value=100,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.sound_level,
            method=lambda device, value: device.set_sound_level(value),
            name="Sound Level",
        ),
    ],
    DockstreamSmartFountain: [
        PetLibroNumberEntityDescription[DockstreamSmartFountain](
            key="water_interval",
            translation_key="water_interval",
            icon="mdi:timer",
            native_unit_of_measurement="m",
            native_max_value=180,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.water_interval,
            method=lambda device, value: device.set_water_interval(value),
            name="Water Interval",
        ),
        PetLibroNumberEntityDescription[DockstreamSmartFountain](
            key="water_dispensing_duration",
            translation_key="water_dispensing_duration",
            icon="mdi:timer",
            native_unit_of_measurement="m",
            native_max_value=180,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.water_dispensing_duration,
            method=lambda device, value: device.set_water_dispensing_duration(value),
            name="Water Dispensing Duration",
        ),
        PetLibroNumberEntityDescription[DockstreamSmartFountain](
            key="cleaning_cycle",
            translation_key="cleaning_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.cleaning_cycle,
            method=lambda device, value: device.set_cleaning_cycle(value),
            name="Cleaning Cycle",
        ),
        PetLibroNumberEntityDescription[DockstreamSmartFountain](
            key="filter_cycle",
            translation_key="filter_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.filter_cycle,
            method=lambda device, value: device.set_filter_cycle(value),
            name="Filter Cycle",
        ),
    ],
    DockstreamSmartRFIDFountain: [
        PetLibroNumberEntityDescription[DockstreamSmartRFIDFountain](
            key="water_interval",
            translation_key="water_interval",
            icon="mdi:timer",
            native_unit_of_measurement="m",
            native_max_value=180,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.water_interval,
            method=lambda device, value: device.set_water_interval(value),
            name="Water Interval",
        ),
        PetLibroNumberEntityDescription[DockstreamSmartRFIDFountain](
            key="water_dispensing_duration",
            translation_key="water_dispensing_duration",
            icon="mdi:timer",
            native_unit_of_measurement="m",
            native_max_value=180,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.water_dispensing_duration,
            method=lambda device, value: device.set_water_dispensing_duration(value),
            name="Water Dispensing Duration",
        ),
        PetLibroNumberEntityDescription[DockstreamSmartRFIDFountain](
            key="cleaning_cycle",
            translation_key="cleaning_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.cleaning_cycle,
            method=lambda device, value: device.set_cleaning_cycle(value),
            name="Cleaning Cycle",
        ),
        PetLibroNumberEntityDescription[DockstreamSmartRFIDFountain](
            key="filter_cycle",
            translation_key="filter_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.filter_cycle,
            method=lambda device, value: device.set_filter_cycle(value),
            name="Filter Cycle",
        ),
    ],
    Dockstream2SmartCordlessFountain: [
        # Not currently suppported by device, hoping firmware update will add this.
        # PetLibroNumberEntityDescription[Dockstream2SmartCordlessFountain](
        #     key="water_sensing_delay",
        #     translation_key="water_sensing_delay",
        #     icon="mdi:timer",
        #     mode="slider",
        #     native_unit_of_measurement="s",
        #     native_max_value=180,
        #     native_min_value=1,
        #     native_step=1,
        #     value_fn=lambda device: device.water_sensing_delay,
        #     method=lambda device, value: device.set_water_sensing_delay(value),
        #     name="Water Sensing Delay"
        # ),
        PetLibroNumberEntityDescription[Dockstream2SmartCordlessFountain](
            key="water_low_threshold",
            translation_key="water_low_threshold",
            icon="mdi:gauge",
            mode=NumberMode.SLIDER,
            name="Water Low Threshold"
        ),
        PetLibroNumberEntityDescription[Dockstream2SmartCordlessFountain](
            key="cleaning_cycle",
            translation_key="cleaning_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.cleaning_cycle,
            method=lambda device, value: device.set_cleaning_cycle(value),
            name="Cleaning Cycle"
        ),
        PetLibroNumberEntityDescription[Dockstream2SmartCordlessFountain](
            key="filter_cycle",
            translation_key="filter_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.filter_cycle,
            method=lambda device, value: device.set_filter_cycle(value),
            name="Filter Cycle"
        ),
    ],
    Dockstream2SmartFountain: [
        # Not currently suppported by device, hoping firmware update will add this.
        # PetLibroNumberEntityDescription[Dockstream2SmartCordlessFountain](
        #     key="water_sensing_delay",
        #     translation_key="water_sensing_delay",
        #     icon="mdi:timer",
        #     mode="slider",
        #     native_unit_of_measurement="s",
        #     native_max_value=180,
        #     native_min_value=1,
        #     native_step=1,
        #     value_fn=lambda device: device.water_sensing_delay,
        #     method=lambda device, value: device.set_water_sensing_delay(value),
        #     name="Water Sensing Delay"
        # ),
        PetLibroNumberEntityDescription[Dockstream2SmartFountain](
            key="water_low_threshold",
            translation_key="water_low_threshold",
            icon="mdi:gauge",
            mode="slider",
            name="Water Low Threshold"
        ),
        PetLibroNumberEntityDescription[Dockstream2SmartFountain](
            key="cleaning_cycle",
            translation_key="cleaning_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.cleaning_cycle,
            method=lambda device, value: device.set_cleaning_cycle(value),
            name="Cleaning Cycle"
        ),
        PetLibroNumberEntityDescription[Dockstream2SmartFountain](
            key="filter_cycle",
            translation_key="filter_cycle",
            icon="mdi:calendar-alert",
            native_unit_of_measurement="Days",
            mode="box",
            native_max_value=60,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.filter_cycle,
            method=lambda device, value: device.set_filter_cycle(value),
            name="Filter Cycle"
        ),
        PetLibroNumberEntityDescription[Dockstream2SmartFountain](
            key="water_interval",
            translation_key="water_interval",
            icon="mdi:timer",
            native_unit_of_measurement="m",
            native_max_value=180,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.water_interval,
            method=lambda device, value: device.set_water_interval(value),
            name="Water Interval"
        ),
        PetLibroNumberEntityDescription[Dockstream2SmartFountain](
            key="water_dispensing_duration",
            translation_key="water_dispensing_duration",
            icon="mdi:timer",
            native_unit_of_measurement="m",
            native_max_value=180,
            native_min_value=1,
            native_step=1,
            value_fn=lambda device: device.water_dispensing_duration,
            method=lambda device, value: device.set_water_dispensing_duration(value),
            name="Water Dispensing Duration"
        ),
    ],
    LumaSmartLitterBox: [
    ],
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # Use ConfigEntry
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO number using config entry."""
    # Retrieve the hub from hass.data that was set up in __init__.py
    hub = hass.data[DOMAIN].get(entry.entry_id)

    if not hub:
        _LOGGER.error("Hub not found for entry: %s", entry.entry_id)
        return

    # Ensure that the devices are loaded (if load_devices is not already called elsewhere)
    if not hub.devices:
        _LOGGER.warning("No devices found in hub during number setup.")
        return

    # Log the contents of the hub data for debugging
    _LOGGER.debug("Hub data: %s", hub)

    devices = hub.devices  # Devices should already be loaded in the hub
    _LOGGER.debug("Devices in hub: %s", devices)

    # Create number entities for each device based on the number map
    entities = [
        PetLibroNumberEntity(device, hub, description)
        for device in devices  # Iterate through devices from the hub
        for device_type, entity_descriptions in DEVICE_NUMBER_MAP.items()
        if isinstance(device, device_type)
        for description in entity_descriptions
    ]

    if not entities:
        _LOGGER.warning("No number entities added, entities list is empty!")
    else:
        # Log the number of entities and their details
        _LOGGER.debug("Adding %d PetLibro number entities", len(entities))
        for entity in entities:
            _LOGGER.debug("Adding number entity: %s for device %s", entity.entity_description.name, entity.device.name)

        # Add number entities to Home Assistant
        async_add_entities(entities)
