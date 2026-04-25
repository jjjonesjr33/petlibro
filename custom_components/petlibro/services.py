"""PETLIBRO feeding plan services."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_EDIT_FEEDING_PLAN       = "edit_feeding_plan"
SERVICE_ADD_FEEDING_PLAN        = "add_feeding_plan"
SERVICE_TOGGLE_FEEDING_PLAN     = "toggle_feeding_plan"
SERVICE_SKIP_FEEDING_PLAN       = "skip_feeding_plan"
SERVICE_DELETE_FEEDING_PLAN     = "delete_feeding_plan"
SERVICE_TOGGLE_FEEDING_SCHEDULE = "toggle_feeding_schedule"
SERVICE_TOGGLE_TODAY_SCHEDULE   = "toggle_today_feeding_schedule"

# Field keys
_DEVICE_ID = "device_id"
_PLAN_ID   = "plan_id"
_TIME      = "time"
_PORTIONS  = "portions"
_LABEL     = "label"
_DAYS      = "days"
_SOUND     = "sound"
_ENABLE    = "enable"
_SKIP      = "skip"


def _get_feeder(hass: HomeAssistant, device_id: str):
    """Resolve a HA device_id to a PetLibro feeder device instance."""
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get(device_id)
    if not device_entry:
        raise ServiceValidationError(
            "Device not found. Please select a dry food feeder."
        )

    serial = next(
        (identifier[1] for identifier in device_entry.identifiers if identifier[0] == DOMAIN),
        None,
    )
    if not serial:
        raise ServiceValidationError(
            "Selected device is not a PETLIBRO device. Please select a dry food feeder."
        )

    for _, hub in hass.data.get(DOMAIN, {}).items():
        device = hub.devices.get(serial)
        if device is not None:
            if not hasattr(device, "feeding_plan_data"):
                raise ServiceValidationError(
                    f"{device.name} does not support feeding plan services. "
                    "Please select a dry food feeder, not a pet or fountain."
                )
            return device

    raise ServiceValidationError(
        "Selected device is not a dry food feeder, or is not currently loaded."
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register PETLIBRO feeding plan services."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_FEEDING_PLAN):
        return  # Already registered

    # ------------------------------------------------------------------
    # edit_feeding_plan
    # ------------------------------------------------------------------
    async def handle_edit_feeding_plan(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])
        plan_id: int = call.data[_PLAN_ID]

        existing = device.feeding_plan_data.get(str(plan_id))
        if not existing:
            raise ServiceValidationError(
                f"Plan ID {plan_id} not found on {device.name}. "
                "Check the Feeding Schedule sensor attributes for valid plan IDs."
            )

        if (label := call.data.get(_LABEL, "")):
            if " " in label:
                raise ServiceValidationError(
                    "Label cannot contain spaces. Use something like 'MorningFeed' instead."
                )

        payload: dict[str, Any] = {**existing, "id": plan_id}
        if (v := call.data.get(_TIME)) is not None:
            payload["executionTime"] = v[:5]
        if (v := call.data.get(_PORTIONS)) is not None:
            payload["grainNum"] = v
        if (v := call.data.get(_LABEL)) is not None:
            payload["label"] = v
        if (v := call.data.get(_DAYS)) is not None:
            payload["repeatDay"] = "[" + ",".join(str(int(d)) for d in v) + "]"
        if (v := call.data.get(_SOUND)) is not None:
            payload["enableAudio"] = v

        await device.api.feeding_plan_update(device.serial, payload)
        await device.refresh()
        _LOGGER.debug("Edited feeding plan %d on %s", plan_id, device.name)

    hass.services.async_register(DOMAIN, SERVICE_EDIT_FEEDING_PLAN, handle_edit_feeding_plan)

    # ------------------------------------------------------------------
    # add_feeding_plan
    # ------------------------------------------------------------------
    async def handle_add_feeding_plan(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])

        if (label := call.data.get(_LABEL, "")):
            if " " in label:
                raise ServiceValidationError(
                    "Label cannot contain spaces. Use something like 'MorningFeed' instead."
                )

        payload: dict[str, Any] = {
            "executionTime": call.data[_TIME][:5],
            "grainNum": call.data[_PORTIONS],
            "label": call.data.get(_LABEL, ""),
            "repeatDay": "[" + ",".join(str(int(d)) for d in call.data.get(_DAYS, [])) + "]",
            "enableAudio": call.data.get(_SOUND, False),
        }
        await device.api.feeding_plan_add(device.serial, payload)
        await device.refresh()
        _LOGGER.debug("Added new feeding plan on %s", device.name)

    hass.services.async_register(DOMAIN, SERVICE_ADD_FEEDING_PLAN, handle_add_feeding_plan)

    # ------------------------------------------------------------------
    # toggle_feeding_plan  (enable / disable a single plan)
    # ------------------------------------------------------------------
    async def handle_toggle_feeding_plan(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])
        plan_id: int = call.data[_PLAN_ID]
        enable: bool = call.data[_ENABLE]

        existing = device.feeding_plan_data.get(str(plan_id))
        if not existing:
            raise ServiceValidationError(
                f"Plan ID {plan_id} not found on {device.name}. "
                "Check the Feeding Schedule sensor attributes for valid plan IDs."
            )

        await device.api.feeding_plan_toggle(
            device.serial,
            {**existing, "id": plan_id, "enable": enable},
        )
        await device.refresh()
        _LOGGER.debug("Toggled plan %d to %s on %s", plan_id, enable, device.name)

    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_FEEDING_PLAN, handle_toggle_feeding_plan)

    # ------------------------------------------------------------------
    # skip_feeding_plan  (skip / un-skip a single plan for today)
    # ------------------------------------------------------------------
    async def handle_skip_feeding_plan(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])
        plan_id: int = call.data[_PLAN_ID]
        skip: bool = call.data[_SKIP]

        await device.api.feeding_plan_today_skip(device.serial, plan_id, skip=skip)
        await device.refresh()
        _LOGGER.debug("Set skip=%s for plan %d on %s", skip, plan_id, device.name)

    hass.services.async_register(DOMAIN, SERVICE_SKIP_FEEDING_PLAN, handle_skip_feeding_plan)

    # ------------------------------------------------------------------
    # delete_feeding_plan  (permanently remove a plan)
    # ------------------------------------------------------------------
    async def handle_delete_feeding_plan(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])
        plan_id: int = call.data[_PLAN_ID]

        existing = device.feeding_plan_data.get(str(plan_id))
        if not existing:
            raise ServiceValidationError(
                f"Plan ID {plan_id} not found on {device.name}. "
                "Check the Feeding Schedule sensor attributes for valid plan IDs."
            )

        await device.api.feeding_plan_delete(device.serial, plan_id)
        await device.refresh()
        _LOGGER.debug("Deleted plan %d on %s", plan_id, device.name)

    hass.services.async_register(DOMAIN, SERVICE_DELETE_FEEDING_PLAN, handle_delete_feeding_plan)

    # ------------------------------------------------------------------
    # toggle_feeding_schedule  (enable / disable the entire schedule)
    # ------------------------------------------------------------------
    async def handle_toggle_feeding_schedule(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])
        enable: bool = call.data[_ENABLE]

        await device.api.set_feeding_plan(device.serial, enable)
        await device.refresh()
        _LOGGER.debug("Toggled entire feeding schedule to %s on %s", enable, device.name)

    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_FEEDING_SCHEDULE, handle_toggle_feeding_schedule)

    # ------------------------------------------------------------------
    # toggle_today_feeding_schedule  (enable / disable all of today's feeds)
    # ------------------------------------------------------------------
    async def handle_toggle_today_schedule(call: ServiceCall) -> None:
        device = _get_feeder(hass, call.data[_DEVICE_ID])
        enable: bool = call.data[_ENABLE]

        await device.api.feeding_plan_today_all(device.serial, enable)
        await device.refresh()
        _LOGGER.debug("Toggled today's schedule to %s on %s", enable, device.name)

    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_TODAY_SCHEDULE, handle_toggle_today_schedule)

    _LOGGER.debug("PETLIBRO feeding plan services registered.")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove PETLIBRO feeding plan services when the integration is unloaded."""
    for service in (
        SERVICE_EDIT_FEEDING_PLAN,
        SERVICE_ADD_FEEDING_PLAN,
        SERVICE_TOGGLE_FEEDING_PLAN,
        SERVICE_SKIP_FEEDING_PLAN,
        SERVICE_DELETE_FEEDING_PLAN,
        SERVICE_TOGGLE_FEEDING_SCHEDULE,
        SERVICE_TOGGLE_TODAY_SCHEDULE,
    ):
        hass.services.async_remove(DOMAIN, service)
    _LOGGER.debug("PETLIBRO feeding plan services removed.")