"""Class to manage entities which use Petlibro measurement units."""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import (
    async_get as get_entity_registry,
    RegistryEntryDisabler,
    RegistryEntryHider
)
from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.components.number.const import NumberDeviceClass

from ..const import (
    SENTINEL as UNDEFINED,
    DOMAIN,
    GITHUB,
    ROUNDING_RULES,
    DEFAULT_PORTIONS_IN_CUP,
    DEFAULT_MAX_FEED_PORTIONS,
    Unit,
    APIKey as API,
    IntegrationSetting,
)
from ..hub import PetLibroHub
from ..devices import Device

_LOGGER = logging.getLogger(__name__)


class Unit_Entities:
    """Manage the entities which use Petlibro measurement units.

    An example of a unit entity is the sensor 'today_feeding_quantity_weight', which syncronises with
    Petlibro Feeder units to display feed quantities in the user's configured feed weight.
    """

    def __init__(self, *, hass: HomeAssistant, config_entry: ConfigEntry, hub: PetLibroHub):
        """Initialise the Unit_Entities class."""
        self.hass = hass
        self.entry = config_entry
        self.handler = self.entry.entry_id
        self.hub = hub
        self.member = self.hub.member
        self.entity_registry = get_entity_registry(self.hass)
        self._sync_task = None

        self.feed_number_unique_ids: dict[Platform, list[str]] = {
            Platform.NUMBER: [], Platform.SELECT: []
        }
        self.unique_ids: dict[API, dict[Platform, dict[SensorDeviceClass, list[str]]]] = {
            API.FEED_UNIT: {
                Platform.SENSOR: {SensorDeviceClass.WEIGHT: [], SensorDeviceClass.VOLUME: []},
                Platform.NUMBER: {NumberDeviceClass.WEIGHT: [], NumberDeviceClass.VOLUME: []},
            },
            API.WEIGHT_UNIT: {
                Platform.SENSOR: {SensorDeviceClass.WEIGHT: []}, 
                Platform.NUMBER: {NumberDeviceClass.WEIGHT: []},
            },
            API.WATER_UNIT: {
                Platform.SENSOR: {SensorDeviceClass.VOLUME: []}, 
                Platform.NUMBER: {NumberDeviceClass.VOLUME: []},
            },
        }
        _LOGGER.debug("Unit Entities Helper initialised.")

    def cups_select_options(self, device: Device | None = None) -> list[str]:
        """Return formatted cup portion options for a select entity."""
        denominator = round(DEFAULT_PORTIONS_IN_CUP / (device.feed_conv_factor if device else 1))
        max_portions = device.max_feed_portions if device else DEFAULT_MAX_FEED_PORTIONS
        numerator_trans = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
        denominator_trans = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
        options = []
        for portion in range(1, max_portions + 1):
            whole, remainder = divmod(portion, denominator)
            if remainder == 0:
                label = f"{whole}"
            else:
                num = str(remainder).translate(numerator_trans)
                den = str(denominator).translate(denominator_trans)
                label = f"{num}/{den}" if whole == 0 else f"{whole} {num}/{den}"
            options.append(label)
        return options

    async def sync_manual_feed_entity_visibility(
        self, /, feed_unit: Unit | None = UNDEFINED, include_portions: bool = True,
    ) -> bool:
        """Enable/disable and hide/unhide manual feed entities based on compatibility.

        Behavior:
        - If `feed_unit` is UNDEFINED, defaults to the member's current feed unit type.
        - If `include_portions` is False, ignores MANUAL_FEED_PORTIONS integration option.
        - SELECT entities are disabled when not using cups or when portions are enabled.
        - NUMBER entities are disabled when using cups without portions.
        - Returns True if the integration needs to be reloaded.
        """

        numbers = self.feed_number_unique_ids.get(Platform.NUMBER)
        selects = self.feed_number_unique_ids.get(Platform.SELECT)
        
        reload_needed = False

        if len(numbers) != len(selects):
            _LOGGER.error(
                "Not all Number entities have an equivalent Select entity, or vice versa. "
                "Please open an issue at %s/issues if the problem persists.\n"
                "Number entities: %s\nSelect entities: %s", GITHUB, numbers, selects
            )
        elif not (numbers and selects):
            # No entities to update
            return False

        feed_unit = self.member.feedUnitType if feed_unit is UNDEFINED else feed_unit
        set_as_portion = (
            self.entry.options.get(IntegrationSetting.MANUAL_FEED_PORTIONS)
            if include_portions
            else False
        )

        def incompatible(platform: Platform) -> bool:
            match platform:
                case Platform.SELECT: return feed_unit != Unit.CUPS or set_as_portion
                case Platform.NUMBER: return feed_unit == Unit.CUPS and not set_as_portion
                case _: raise ValueError(f"Unsupported platform: {platform}")

        for platform, unique_ids in self.feed_number_unique_ids.items():
            entity_ids = []
            not_found = []

            for unique_id in unique_ids:
                if entity_id := self.entity_registry.async_get_entity_id(platform, DOMAIN, unique_id):
                    entity_ids.append(entity_id)
                else:
                    not_found.append(unique_id)

            if not_found:
                _LOGGER.warning("Manual feed entities not found for %s: %s", platform, not_found)

            if not entity_ids:
                continue

            incompat = incompatible(platform)
            disable = RegistryEntryDisabler.INTEGRATION if incompat else None
            hide = RegistryEntryHider.INTEGRATION if incompat else None

            action = "Hiding/disabling incompatible" if incompat else "Unhiding/enabling compatible"
            _LOGGER.debug("%s entities for %s: %s", action, platform, entity_ids)


            for entity_id in entity_ids:
                if self.entity_registry.async_get(entity_id).disabled_by != disable:
                    reload_needed = True
                    _LOGGER.debug("Integration reload needed for entity: %s", entity_id)
                else:
                    _LOGGER.debug("Entity '%s' already %s, no reload needed", entity_id, "disabled" if disable else "enabled")
                self.entity_registry.async_update_entity(entity_id, disabled_by=disable, hidden_by=hide)

        return reload_needed

    @callback
    def schedule_manual_feed_sync(self) -> None:
        """Debounce manual feed entity visibility sync calls to avoid redundant calls."""
        if not self._sync_task or self._sync_task.done():
            self._sync_task = self.hass.async_create_task(self._run_manual_feed_sync())

    async def _run_manual_feed_sync(self) -> None:
        """Run the sync_manual_feed_entity_visibility method with default args and reload if needed."""
        reload_needed = await self.sync_manual_feed_entity_visibility()
        if reload_needed:
            await self.hub.async_refresh(force_member=True)

    async def update_sensor_entity_units(
        self, /, new_units: dict[API|str, Unit] = UNDEFINED, update_all_units: bool = False
    ) -> bool:
        """Update all sensor entity units which use Petlibro's feed, weight or water units based on account settings.

        Behavior:
        - If `new_units` is UNDEFINED, defaults to all three of the member's current unit types.
        - If `update_all_units` is True, updates all sensor entity units, and will default \
          to the member's current unit type for any not provided in `new_units`.
        - Returns True if the integration needs to be reloaded.
        """

        if new_units is UNDEFINED:
            update_all_units = True
            new_units = {}

        if not (new_units or update_all_units):
            return False

        reload_needed = False

        for unit_type, platforms in self.unique_ids.items():
            selected = new_units.get(unit_type)
            unit = (
                selected if isinstance(selected, Unit)
                else Unit(selected) if selected
                else getattr(self.member, unit_type, None)
            )
            if not update_all_units and (unit_type not in new_units or not unit):
                continue

            _LOGGER.debug("Updating %s entities", unit_type)

            target_units = (
                {"weight": unit if unit and unit.device_class == "weight" else Unit.GRAMS,
                "volume": unit if unit and unit.device_class == "volume" else Unit.MILLILITERS}
                if update_all_units and unit_type == API.FEED_UNIT
                else {unit.device_class: unit} if unit and unit.device_class else {}
            )

            for platform, unit_classes in platforms.items():
                for device_class, unique_ids in unit_classes.items():
                    if not (target_unit := target_units.get(device_class)):
                        continue
                    precision = ROUNDING_RULES.get(target_unit, 0)
                    options = {
                        "unit_of_measurement": target_unit.symbol,
                        "display_precision": precision,
                        "suggested_display_precision": precision,
                    }
                    for unique_id in unique_ids:
                        entity_id = self.entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
                        if not entity_id:
                            continue
                        _LOGGER.debug(
                            "Setting %s to %s with display precision %s",
                            entity_id, target_unit.symbol, precision,
                        )
                        self.entity_registry.async_update_entity_options(entity_id, platform, options)

            if unit_type is API.FEED_UNIT and (
                (
                    Unit.CUPS in (unit, self.member.feedUnitType)
                    and not self.entry.options.get(
                        IntegrationSetting.MANUAL_FEED_PORTIONS
                    )
                )
                or update_all_units
            ):
                try:
                    reload_needed = await self.sync_manual_feed_entity_visibility(unit)
                except HomeAssistantError as e:
                    _LOGGER.error("Error syncing manual feed entity visibility: %s", e)

        _LOGGER.debug("Unit entity update complete (reload=%s)", reload_needed)
        return reload_needed
