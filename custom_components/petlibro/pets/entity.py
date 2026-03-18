"""Pet object representing pet(s) on the user's Petlibro account."""

from __future__ import annotations
from collections.abc import Callable
from datetime import date
from functools import cached_property
from logging import getLogger
from pathlib import Path
import sys
from typing import Any

from homeassistant.util.dt import utcnow
from homeassistant.const import (
    EntityCategory,
    Platform,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.components.date import DateEntity, DateEntityDescription
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    dataclass,
)
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.event import async_call_later

from .const import DEFAULT_PET_AVATAR, PetAPIKey as PetAPI
from ..const import (
    DOMAIN,
    APIKey as API,
    Gender,
    IntegrationSetting,
    Unit,
)
from ..devices.event import EVENT_UPDATE
from ..member import Member
from . import Pet

_LOGGER = getLogger(__name__)


# Base Entity ------------------
class PL_PetEntityDescription(EntityDescription):
    """Pet Entity description."""

    value_fn: Callable[[Pet]] = lambda _: None
    set_fn: Callable[[Pet, Any | date]] = lambda p, _: None
    icon_fn: Callable[[Pet]] = lambda _: None
    native_unit_of_measurement_fn: Callable[[Member]] = lambda _: None
    suggested_unit_of_measurement_fn: Callable[[Member]] = lambda _: None
    device_class_fn: Callable[[Pet], SensorDeviceClass | NumberDeviceClass | None] = (
        lambda _: None
    )
    extra_state_attributes_fn: Callable[[Pet], dict | None] = lambda _: None
    available_fn: Callable[[Pet, bool], bool] = lambda p, _: None
    entity_registry_visible_default_fn: Callable[[Pet, bool], bool] = lambda p, _: None
    entity_registry_enabled_default_fn: Callable[[Pet, bool], bool] = lambda p, _: None
    petlibro_unit: API | str | None = None


class PL_PetEntity(CoordinatorEntity[DataUpdateCoordinator[bool]]):
    """Pet Base Entity."""

    def __init__(self, pet: Pet, hub, description) -> None:
        """Initialise the pet entity."""
        if "PetLibroHub" not in sys.modules:
            from ..hub import PetLibroHub
        self.pet = pet
        self.hub: PetLibroHub = hub
        self.helper = self.hub.pets_helper
        self.entity_description: PL_PetEntityDescription = description
        self.desc = self.entity_description
        self.member = self.hub.member
        self.api = self.hub.api
        self._attr_unique_id = f"{DOMAIN}-{self.desc.key}-{self.pet.id}"
        self._attr_has_entity_name = True
        self._buffer_value = None
        super().__init__(self.hub.coordinator)

        if not self.pet.device_id:
            self.pet.set_device_id()
        if not self.pet.saved_to_options:
            self.pet.save_to_options()

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers=self.pet.device_identifiers,
            manufacturer=DOMAIN.capitalize(),
            name=self.pet.name,
            entry_type=DeviceEntryType.SERVICE,
            model="Pet",
            model_id=str(self.pet.id),
        )

    @cached_property
    def translation_key(self) -> str | None:
        if not self.desc.translation_key:
            return self.desc.key
        return super().translation_key

    @property
    def native_value(self) -> Any:
        if self.desc.key == "feedingGoal":
            return (
                Unit.convert_feed(
                    value=self.pet.feedingGoal,
                    from_unit=None,
                    to_unit=self.pet.member.feedUnitType,
                    rounded=True,
                )
                if not self.portions_enabled
                else self.pet.feedingGoal
            )

        return (
            self._buffer_value
            if self._buffer_value
            else value_fn
            if (value_fn := self.desc.value_fn(self.pet)) is not None
            else pet_attr
            if (pet_attr := getattr(self.pet, self.desc.key, None)) is not None
            else getattr(super(), "native_value", None)
        )

    @property
    def is_on(self) -> bool | None:
        return bool(getattr(self.pet, self.desc.key, None))

    @property
    def icon(self) -> str | None:
        return self.desc.icon_fn(self.pet) or super().icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.desc.key == "feedingGoal":
            return (
                self.member.feedUnitType.symbol
                if not self.portions_enabled
                else "portions"
            )

        return self.desc.native_unit_of_measurement_fn(self.member) or getattr(
            super(), "native_unit_of_measurement", None
        )

    @property
    def suggested_unit_of_measurement(self) -> str | None:
        return self.desc.suggested_unit_of_measurement_fn(self.member) or getattr(
            super(), "suggested_unit_of_measurement", None
        )

    @property
    def device_class(self) -> SensorDeviceClass | NumberDeviceClass | str | None:
        return self.desc.device_class_fn(self.pet) or super().device_class

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return (
            self.desc.extra_state_attributes_fn(self.pet)
            or super().extra_state_attributes
        )

    @property
    def available(self) -> bool:
        return (
            self.desc.available_fn(self.pet, self.enable_for_manual_feed)
            or super().available
        )

    @property
    def entity_registry_visible_default(self) -> bool:
        return (
            self.desc.entity_registry_visible_default_fn(
                self.pet, self.enable_for_manual_feed
            )
            or super().entity_registry_visible_default
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        return (
            self.desc.entity_registry_enabled_default_fn(
                self.pet, self.enable_for_manual_feed
            )
            or super().entity_registry_enabled_default
        )

    @property
    def portions_enabled(self) -> bool:
        """Return True if portions are enabled for setting manual feed."""
        return self.hub.entry.options.get(
            IntegrationSetting.MANUAL_FEED_PORTIONS,
            IntegrationSetting.MANUAL_FEED_PORTIONS.default,
        )

    @property
    def enable_for_manual_feed(self) -> bool:
        """Return True if entity should be enabled for manual feed setting."""
        if (
            self.desc.petlibro_unit != API.FEED_UNIT
            or "feedingGoal" not in self.desc.key
        ):
            return True

        domain = self.platform_data.domain
        if domain == Platform.NUMBER:
            return self.member.feedUnitType is not Unit.CUPS or self.portions_enabled
        if domain == Platform.SELECT:
            return self.member.feedUnitType is Unit.CUPS and not self.portions_enabled

    async def async_set_value(self, value: date | Any) -> None:
        """Value was changed on the frontend."""
        await self.desc.set_fn(self.pet, value)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.pet.on(EVENT_UPDATE, self.async_write_ha_state))

    def _handle_coordinator_update(self) -> None:
        if (
            "feedingGoal" in self.desc.key
            and self.enabled != self.enable_for_manual_feed
        ):
            self.hub.unit_entities.schedule_manual_feed_sync()
            _LOGGER.warning("Feed unit mismatch, reloading integration.")

        if self.enabled:
            super()._handle_coordinator_update()


# Sensor Entity ----------------
@dataclass(frozen=True)
class PL_PetSensorEntityDescription(SensorEntityDescription, PL_PetEntityDescription):
    """Pet Sensor Entity description"""


class PL_PetSensorEntity(PL_PetEntity, SensorEntity):
    """Pet Sensor Entity."""

    entity_description: PL_PetSensorEntityDescription

    def __init__(self, pet, hub, description) -> None:
        super().__init__(pet, hub, description)
        self.desc = self.entity_description

        # Set up Unit System functionality
        if (unit_type := self.desc.petlibro_unit) and (
            device_class := self.desc.device_class
        ):
            self.hub.unit_entities.unique_ids[unit_type][Platform.SENSOR][
                device_class
            ].append(self._attr_unique_id)


# Date Entity ------------------
@dataclass(frozen=True)
class PL_PetDateEntityDescription(DateEntityDescription, PL_PetEntityDescription):
    """Pet Date Entity description"""


class PL_PetDateEntity(PL_PetEntity, DateEntity):
    """Pet Date Entity."""


# Switch Entity ----------------
@dataclass(frozen=True)
class PL_PetSwitchEntityDescription(SwitchEntityDescription, PL_PetEntityDescription):
    """Pet Switch Entity description"""


class PL_PetSwitchEntity(PL_PetEntity, SwitchEntity):
    """Pet Switch Entity."""

    entity_description: PL_PetSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.pet, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.pet, False)


# Number Entity ----------------
@dataclass(frozen=True)
class PL_PetNumberEntityDescription(NumberEntityDescription, PL_PetEntityDescription):
    """Pet Number Entity description"""


class PL_PetNumberEntity(PL_PetEntity, NumberEntity):
    """Pet Number Entity."""

    entity_description: PL_PetNumberEntityDescription
    DEBOUNCE_SECONDS = 2
    _debounce = None

    def __init__(self, pet, hub, description) -> None:
        super().__init__(pet, hub, description)
        self.desc = self.entity_description

        # Set up Unit System functionality
        if (
            (unit_type := self.desc.petlibro_unit)
            and unit_type != API.FEED_UNIT
            and (device_class := self.desc.device_class)
        ):
            self.hub.unit_entities.unique_ids[unit_type][Platform.NUMBER][
                device_class
            ].append(self._attr_unique_id)

        elif unit_type == API.FEED_UNIT:
            self.hub.unit_entities.feed_number_unique_ids[Platform.NUMBER].append(
                self._attr_unique_id
            )

    @property
    def native_min_value(self) -> float:
        if self.desc.key == "feedingGoal":
            return (
                self.pet.member.feedUnitType.factor if not self.portions_enabled else 1
            )
        return super().native_min_value

    @property
    def native_max_value(self) -> float:
        if self.desc.key == "feedingGoal":
            return (
                (self.pet.member.feedUnitType.factor * 48)
                if not self.portions_enabled
                else 48
            )
        return super().native_max_value

    @property
    def native_step(self) -> float:
        if self.desc.key == "feedingGoal":
            return (
                self.pet.member.feedUnitType.factor if not self.portions_enabled else 1
            )
        return super().native_step

    async def async_set_native_value(self, value: float) -> None:
        if self._debounce:
            # Cancel any pending API call
            self._debounce()
            self._debounce = None

        self._buffer_value = value
        self.async_write_ha_state()
        # Buffer to prevent spamming API calls
        self._debounce = async_call_later(
            self.hass, self.DEBOUNCE_SECONDS, self._set_value_buffer
        )

    async def _set_value_buffer(self, *args) -> None:
        """Make the API call after buffer time (DEBOUNCE_SECONDS)."""
        self._debounce = None

        if self.desc.key == "feedingGoal":
            await self.pet.update_pet_goal(
                pet_id=self.pet.id,
                goal_name="feedingGoal",
                value=round(
                    Unit.convert_feed(
                        value=self._buffer_value,
                        from_unit=self.pet.member.feedUnitType,
                        to_unit=None,
                    )
                    if not self.portions_enabled
                    else self._buffer_value
                ),
            )
            return

        await self.desc.set_fn(self.pet, self._buffer_value)


# Select Entity ----------------
@dataclass(frozen=True)
class PL_PetSelectEntityDescription(SelectEntityDescription, PL_PetEntityDescription):
    """Pet Select Entity description"""

    options_fn: Callable[[Pet], list] = lambda _: None
    current_option_fn: Callable[[Pet], str] = lambda _: None


class PL_PetSelectEntity(PL_PetEntity, SelectEntity):
    """Pet Select Entity."""

    entity_description: PL_PetSelectEntityDescription

    def __init__(self, pet, hub, description) -> None:
        super().__init__(pet, hub, description)
        self.desc = self.entity_description

        # Set up Unit System functionality
        if self.desc.petlibro_unit == API.FEED_UNIT:
            self.hub.unit_entities.feed_number_unique_ids[Platform.SELECT].append(
                self._attr_unique_id
            )

    @property
    def options(self) -> list[str]:
        return self.desc.options_fn(self.pet) or super().options

    @property
    def current_option(self) -> str | None:
        return self.desc.current_option_fn(self.pet) or super().current_option

    async def async_select_option(self, option: str) -> None:
        await self.desc.set_fn(self.pet, option)


# Image Entity -----------------
@dataclass(frozen=True)
class PL_PetImageEntityDescription(ImageEntityDescription, PL_PetEntityDescription):
    """Pet Image Entity description"""

    image_url_fn: Callable[[Pet], str | None] = lambda _: None


class PL_PetImageEntity(PL_PetEntity, ImageEntity):
    """Pet Image Entity."""

    entity_description: PL_PetImageEntityDescription

    def __init__(self, pet: Pet, hub, description) -> None:
        super().__init__(pet, hub, description)
        ImageEntity.__init__(self, hub.hass)
        self.desc = self.entity_description
        self._attr_image_last_updated = utcnow()
        self._image_url: str = ""
        self._image_bytes: bytes | None = None

    async def async_image(self) -> bytes | None:
        return self._image_bytes

    def _handle_coordinator_update(self) -> None:
        url = self.desc.image_url_fn(self.pet)
        if url != self._image_url:
            # Petlibro provides avatars without image metadata, so the
            # native image_url attribute fails. Therefore, we get it manually.
            self.hass.async_create_task(self._async_update_avatar(url))
        super()._handle_coordinator_update()

    async def _async_update_avatar(self, url: str | None) -> None:
        """Fetch avatar bytes and update image state."""
        image_bytes = None
        try:
            if url:
                async with self.api.session.websession.get(url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
            if not image_bytes:
                path = (
                    Path(self.hass.config.config_dir)
                    / "custom_components"
                    / DOMAIN
                    / DEFAULT_PET_AVATAR
                )
                image_bytes = await self.hass.async_add_executor_job(path.read_bytes)
            self._image_url = url
            self._image_bytes = image_bytes
            self._cached_image = None
            self._attr_image_last_updated = utcnow()
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.warning("Failed to fetch avatar: %s", e)


PET_ENTITY_MAP: dict[PL_PetEntity, tuple[PL_PetEntityDescription]] = {
    PL_PetSensorEntity: (
        PL_PetSensorEntityDescription(
            key="pet",
            icon="mdi:tag-text",
            value_fn=lambda pet: pet.name,
            extra_state_attributes_fn=lambda pet: {
                PetAPI.ID: pet.id,
                PetAPI.MEMBER_ID: pet.memberId,
                PetAPI.PET_TYPE: pet.type.value,
                PetAPI.BREED_ID: pet.breedId,
                PetAPI.NAME: pet.name,
                PetAPI.SEX: pet.gender.value,
                PetAPI.STERILIZATION: 1 if pet.sterilization else 2,
                PetAPI.TODAY_EAT_AMOUNT: pet.todayEatNum,
                "status": pet._data.get("status"),
                PetAPI.RFID: pet.rfid,
                "mainPet": pet._data.get("mainPet"),
            },
        ),
        PL_PetSensorEntityDescription(
            key=PetAPI.PET_TYPE,
            name="Pet type",
            icon_fn=lambda pet: pet.type.icon,
            value_fn=lambda pet: pet.type.name.capitalize(),
        ),
        PL_PetSensorEntityDescription(
            key=PetAPI.BREED_NAME,
            name="Breed",
            translation_key="breed_name",
            icon_fn=lambda pet: pet.type.icon,
        ),
        PL_PetSensorEntityDescription(
            key="todayFeedTimes",
            translation_key="today_feeding_times",
            name="Today's Feeding Times",
            icon="mdi:history",
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        PL_PetSensorEntityDescription(
            key=f"{PetAPI.TODAY_EAT_AMOUNT}_weight",
            translation_key="today_feeding_quantity_weight",
            name="Today's Feeding Quantity (Weight)",
            icon="mdi:scale",
            value_fn=lambda pet: Unit.convert_feed(
                value=pet.todayEatNum,
                from_unit=None,
                to_unit=Unit.GRAMS,
                rounded=True,
            ),
            native_unit_of_measurement=UnitOfMass.GRAMS,
            suggested_unit_of_measurement_fn=lambda member: getattr(
                UnitOfMass, member.feedUnitType.name, None
            ),
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.TOTAL_INCREASING,
            extra_state_attributes_fn=lambda pet: {
                unit.symbol: Unit.convert_feed(
                    value=pet.todayEatNum,
                    from_unit=None,
                    to_unit=unit,
                    rounded=True,
                )
                for unit in (Unit.GRAMS, Unit.OUNCES)
            },
            petlibro_unit=API.FEED_UNIT,
        ),
        PL_PetSensorEntityDescription(
            key=f"{PetAPI.TODAY_EAT_AMOUNT}_volume",
            translation_key="today_feeding_quantity_volume",
            name="Today's Feeding Quantity (Volume)",
            icon="mdi:scale",
            value_fn=lambda pet: Unit.convert_feed(
                value=pet.todayEatNum,
                from_unit=None,
                to_unit=Unit.MILLILITERS,
                rounded=True,
            ),
            native_unit_of_measurement=UnitOfVolume.MILLILITERS,
            suggested_unit_of_measurement_fn=lambda member: getattr(
                UnitOfVolume, member.feedUnitType.name, None
            ),
            device_class=SensorDeviceClass.VOLUME,
            state_class=SensorStateClass.TOTAL_INCREASING,
            extra_state_attributes_fn=lambda pet: {
                unit.symbol: Unit.convert_feed(
                    value=pet.todayEatNum,
                    from_unit=None,
                    to_unit=unit,
                    rounded=True,
                )
                for unit in (Unit.CUPS, Unit.MILLILITERS)
            },
            petlibro_unit=API.FEED_UNIT,
        ),
        PL_PetSensorEntityDescription(
            key=PetAPI.RFID,
            name="RFID Collar",
            icon_fn=lambda pet: "mdi:tag" if pet.rfid else "mdi:tag-off",
            value_fn=lambda pet: pet.rfid[-6:] if pet.rfid else "",
            device_class_fn=lambda pet: "rfid_bound" if pet.rfid else "rfid_unbound",
            extra_state_attributes_fn=lambda pet: {"Full RFID": pet.rfid or ""},
        ),
        PL_PetSensorEntityDescription(
            key="boundDeviceNums",
            translation_key="bound_device_nums",
            name="Linked Devices",
            icon="mdi:devices",
            extra_state_attributes_fn=lambda pet: {
                device.get(API.DEVICE_SN, f"Device {i}"): {
                    "name": device.get("name"),
                    "product_name": device.get("productName"),
                    "product_id": device.get(API.PRODUCT_ID),
                    "ha_device_id": pet.hub.devices_helper.cached_devices.get(
                        device.get(API.DEVICE_SN), {}
                    ).get("device_id")
                    or "",
                }
                for i, device in enumerate(pet.boundDevices)
            },
        ),
        PL_PetSensorEntityDescription(
            key="age",
            name="Age",
            icon="mdi:cake-variant",
            value_fn=lambda pet: pet.age.years,
            extra_state_attributes_fn=lambda pet: {
                "years": pet.age.years,
                "months": pet.age.months,
                "days": pet.age.days,
                "days_until_birthday": (bday - today).days
                if (bday := pet.birthday.replace(year=(today := date.today()).year))
                >= today
                else (bday.replace(year=today.year + 1) - today).days,
            },
        ),
    ),
    PL_PetImageEntity: (
        PL_PetImageEntityDescription(
            key=PetAPI.AVATAR,
            name="Avatar",
            image_url_fn=lambda pet: pet.avatar,
            extra_state_attributes_fn=lambda pet: {"url": pet.avatar},
        ),
    ),
    PL_PetDateEntity: (
        PL_PetDateEntityDescription(
            key=PetAPI.BIRTHDAY,
            name="Date of Birth",
            icon="mdi:cake-variant",
            entity_category=EntityCategory.CONFIG,
            set_fn=lambda pet, date: pet.update_pet_settings(
                {PetAPI.BIRTHDAY: pet.to_api_birthday(date)}
            ),
        ),
    ),
    PL_PetSwitchEntity: (
        PL_PetSwitchEntityDescription(
            key=PetAPI.STERILIZATION,
            name="Neutered/Spayed",
            icon="mdi:diameter-variant",
            entity_category=EntityCategory.CONFIG,
            set_fn=lambda pet, value: pet.update_pet_settings(
                {PetAPI.STERILIZATION: (1 if value else 2)}  # 1=True, 2=False
            ),
        ),
    ),
    PL_PetNumberEntity: (
        PL_PetNumberEntityDescription(
            key=PetAPI.WEIGHT,
            name="Current Weight",
            native_min_value=0.2,
            native_max_value=250,
            native_step=0.1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.WEIGHT,
            icon="mdi:weight",
            native_unit_of_measurement=UnitOfMass.KILOGRAMS,
            suggested_unit_of_measurement_fn=lambda member: (
                member.weightUnitType.symbol
            ),
            set_fn=lambda pet, value: pet.update_pet_settings({PetAPI.WEIGHT: value}),
            petlibro_unit=API.WEIGHT_UNIT,
        ),
        PL_PetNumberEntityDescription(
            key="feedingGoal",
            translation_key="feeding_goal",
            name="Dry Food Goal",
            icon="mdi:bowl",
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
            available_fn=lambda _, enable: enable,
            entity_registry_visible_default_fn=lambda _, enable: enable,
            entity_registry_enabled_default_fn=lambda _, enable: enable,
            petlibro_unit=API.FEED_UNIT,
        ),
        PL_PetNumberEntityDescription(
            key="drinkingGoal",
            translation_key="drinking_goal",
            name="Drinking Goal",
            native_min_value=0,
            native_max_value=2500,
            native_step=1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.VOLUME,
            icon="mdi:water",
            native_unit_of_measurement=UnitOfVolume.MILLILITERS,
            suggested_unit_of_measurement_fn=lambda member: member.waterUnitType.symbol,
            set_fn=lambda pet, value: pet.update_pet_goal(
                pet.id, "drinkingGoal", value
            ),
            petlibro_unit=API.WATER_UNIT,
        ),
        PL_PetNumberEntityDescription(
            key="weightGoal",
            translation_key="weight_goal",
            name="Weight Goal",
            native_min_value=0,
            native_max_value=114,
            native_step=0.1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.WEIGHT,
            icon="mdi:scale-bathroom",
            native_unit_of_measurement=UnitOfMass.KILOGRAMS,
            suggested_unit_of_measurement_fn=lambda member: (
                member.weightUnitType.symbol
            ),
            set_fn=lambda pet, value: pet.update_pet_goal(pet.id, "weightGoal", value),
            petlibro_unit=API.WEIGHT_UNIT,
        ),
        PL_PetNumberEntityDescription(
            key="trainingGoal",
            translation_key="training_goal",
            name="Training Goal",
            native_min_value=1,
            native_max_value=1440,
            native_step=1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            icon="mdi:weight-lifter",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            set_fn=lambda pet, value: pet.update_pet_goal(
                pet.id, "trainingGoal", value
            ),
        ),
        PL_PetNumberEntityDescription(
            key="playingGoal",
            translation_key="playing_goal",
            name="Playing Goal",
            native_min_value=1,
            native_max_value=1440,
            native_step=1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            icon="mdi:teddy-bear",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            set_fn=lambda pet, value: pet.update_pet_goal(pet.id, "playingGoal", value),
        ),
        PL_PetNumberEntityDescription(
            key="walkingGoal",
            translation_key="walking_goal",
            name="Walking Goal",
            native_min_value=1,
            native_max_value=1440,
            native_step=1,
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            icon="mdi:walk",
            native_unit_of_measurement=UnitOfTime.MINUTES,
            set_fn=lambda pet, value: pet.update_pet_goal(pet.id, "walkingGoal", value),
        ),
    ),
    PL_PetSelectEntity: (
        PL_PetSelectEntityDescription(
            key=PetAPI.SEX,
            translation_key="pet_sex",
            name="Sex",
            icon_fn=lambda pet: pet.gender.icon,
            entity_category=EntityCategory.CONFIG,
            options=["none", "male", "female"],
            current_option_fn=lambda pet: pet.gender.lower if pet.gender else "none",
            set_fn=lambda pet, option: pet.update_pet_settings(
                {PetAPI.SEX: Gender[str(option).upper()] if option != "none" else None}
            ),
        ),
        PL_PetSelectEntityDescription(
            key="feedingGoal_cups",
            translation_key="feeding_goal",
            name="Dry Food Goal",
            icon="mdi:bowl",
            entity_category=EntityCategory.CONFIG,
            options_fn=lambda pet: pet.hub.unit_entities.cups_select_options(),
            current_option_fn=lambda pet: pet.hub.unit_entities.cups_select_options()[
                round((pet.feedingGoal or 1) - 1)
            ],
            unit_of_measurement=Unit.CUPS.symbol,
            available_fn=lambda _, enable: enable,
            entity_registry_visible_default_fn=lambda _, enable: enable,
            entity_registry_enabled_default_fn=lambda _, enable: enable,
            set_fn=lambda pet, value: pet.update_pet_goal(
                pet_id=pet.id,
                goal_name="feedingGoal",
                value=pet.hub.unit_entities.cups_select_options().index(value) + 1,
            ),
            petlibro_unit=API.FEED_UNIT,
        ),
    ),
}
