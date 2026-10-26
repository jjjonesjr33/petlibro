"""Support for PETLIBRO event entities (motion / sound alerts)."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices.feeders.granary_smart_camera_feeder import GranarySmartCameraFeeder
from .entity import PetLibroEntity, PetLibroEntityDescription, _DeviceT
from .devices.event import EVENT_UPDATE
from .hub import PetLibroHub

_LOGGER = logging.getLogger(__name__)

# Event types fired by the detection event entities.
EVENT_TYPE_MOTION = "motion_detected"
EVENT_TYPE_SOUND = "sound_detected"


@dataclass(frozen=True, kw_only=True)
class PetLibroEventEntityDescription(EventEntityDescription, PetLibroEntityDescription[_DeviceT]):
    """Describes a PETLIBRO event entity."""

    detections_attr: str
    event_type: str


class PetLibroDetectionEventEntity(PetLibroEntity[_DeviceT], EventEntity):
    """Fires once for every new message-center alert of one kind."""

    entity_description: PetLibroEventEntityDescription[_DeviceT]

    def __init__(self, device, hub, description) -> None:
        super().__init__(device, hub, description)
        self._attr_event_types = [description.event_type]
        # Newest alert already seen. Seeded from the first poll so existing
        # history is not replayed after a restart.
        self._last_timestamp: int | None = None

    def _detections(self) -> list[dict]:
        return getattr(self.device, self.entity_description.detections_attr)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Existing history counts as seen: seed from data loaded before setup.
        if self.device._data.get("messages") is not None:
            detections = self._detections()
            self._last_timestamp = detections[0]["timestamp"] if detections else 0
        # PetLibroEntity entities update on the device's own update signal.
        self.async_on_remove(self.device.on(EVENT_UPDATE, self._fire_new_detections))

    @callback
    def _fire_new_detections(self) -> None:
        if self._last_timestamp is None:
            if self.device._data.get("messages") is not None:
                detections = self._detections()
                self._last_timestamp = detections[0]["timestamp"] if detections else 0
            return
        new = [d for d in self._detections() if d["timestamp"] > self._last_timestamp]
        for detection in sorted(new, key=lambda d: d["timestamp"]):
            self._last_timestamp = detection["timestamp"]
            self._trigger_event(
                self.entity_description.event_type,
                {"message_id": detection["id"], "detected_at": detection["time"].isoformat()},
            )


DEVICE_EVENT_MAP: dict[type, list[PetLibroEventEntityDescription]] = {
    GranarySmartCameraFeeder: [
        PetLibroEventEntityDescription[GranarySmartCameraFeeder](
            key="motion_event",
            translation_key="motion_event",
            icon="mdi:motion-sensor",
            device_class=EventDeviceClass.MOTION,
            detections_attr="motion_detections",
            event_type=EVENT_TYPE_MOTION,
            name="Motion",
        ),
        PetLibroEventEntityDescription[GranarySmartCameraFeeder](
            key="sound_event",
            translation_key="sound_event",
            icon="mdi:ear-hearing",
            detections_attr="sound_detections",
            event_type=EVENT_TYPE_SOUND,
            name="Sound",
        ),
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PETLIBRO event entities using config entry."""
    hub: PetLibroHub = hass.data[DOMAIN].get(entry.entry_id)
    if not hub or not hub.devices:
        return

    entities = [
        PetLibroDetectionEventEntity(device, hub, description)
        for device in hub.devices.values()
        for device_type, descriptions in DEVICE_EVENT_MAP.items()
        if isinstance(device, device_type)
        for description in descriptions
    ]
    if entities:
        async_add_entities(entities)
