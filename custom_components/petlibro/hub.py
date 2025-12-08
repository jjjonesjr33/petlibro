"""Petlibro hub."""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Any

from homeassistant.components.sensor.const import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PetLibroAPI
from .const import UPDATE_INTERVAL_SECONDS, APIKey
from .devices import Device, product_name_map
from .member import Member

_LOGGER = getLogger(__name__)


class PetLibroHub:
    """A PetLibro hub wrapper class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the PetLibro Hub."""
        self.hass = hass
        self.entry = config_entry
        self._data = self.entry.data
        self.devices: list[Device] = []  # Initialize devices as an instance variable
        self.member: Member = None
        self.last_refresh_times = {}  # Track the last refresh time for the member & each device
        self.loaded_device_sn = (
            set()
        )  # Track device serial numbers that have already been loaded
        self._last_online_status = {}  # Store online status per device

        self.manual_feed_unique_ids: dict[Platform, list[str]] = {
            Platform.NUMBER: [],
            Platform.SELECT: [],
        }
        self.unit_sensor_unique_ids: dict[
            APIKey, dict[SensorDeviceClass, list[str]]
        ] = {
            APIKey.FEED_UNIT: {
                SensorDeviceClass.WEIGHT: [],
                SensorDeviceClass.VOLUME: [],
            },
            APIKey.WEIGHT_UNIT: {SensorDeviceClass.WEIGHT: []},
            APIKey.WATER_UNIT: {SensorDeviceClass.VOLUME: []},
        }

        # Fetch email, password, and region from entry.data
        email = self.entry.data.get(CONF_EMAIL)
        password = self.entry.data.get(CONF_PASSWORD)
        region = self.entry.data.get(CONF_REGION)

        # Check if the required information is provided
        if not email:
            _LOGGER.error("Email is missing in the configuration entry.")
            msg = "Email is required to initialize PetLibroAPI."
            raise ValueError(msg)
        if not password:
            _LOGGER.error("Password is missing in the configuration entry.")
            msg = "Password is required to initialize PetLibroAPI."
            raise ValueError(msg)
        if not region:
            _LOGGER.error("Region is missing in the configuration entry.")
            msg = "Region is required to initialize PetLibroAPI."
            raise ValueError(msg)

        _LOGGER.debug(
            "Initializing PetLibroAPI with email: %s, region: %s", email, region
        )

        # Initialize the PetLibro API instance
        self.api = PetLibroAPI(
            async_get_clientsession(hass),
            hass.config.time_zone,
            region,
            email,
            password,
            self.entry.data.get(CONF_API_TOKEN),
        )

        # Setup DataUpdateCoordinator to periodically refresh device data
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="petlibro_data",
            update_method=self.refresh_data,  # Calls the refresh_data method
            update_interval=timedelta(
                seconds=UPDATE_INTERVAL_SECONDS
            ),  # Use defined interval
        )

    async def load_devices(self) -> None:
        """Load devices from the API and initialize them."""
        try:
            device_list = await self.api.list_devices()
            _LOGGER.debug("Fetched %s devices from the API.", len(device_list))

            if not device_list:
                _LOGGER.warning("No devices found in the API response.")
                return  # Early return if no devices found

            for device_data in device_list:
                device_sn = device_data.get("deviceSn", "unknown")
                device_name = device_data.get("productName", "unknown")
                _LOGGER.debug(
                    "Processing device: %s (Serial: %s)", device_name, device_sn
                )

                # Check if the device is already loaded
                if device_sn in self.loaded_device_sn:
                    _LOGGER.debug(
                        "Device %s is already loaded, skipping further initialization.",
                        device_sn,
                    )
                    continue

                # Create a new device and add it without calling refresh immediately
                if device_name in product_name_map:
                    _LOGGER.debug(
                        "Loading new device: %s (Serial: %s)", device_name, device_sn
                    )
                    device = product_name_map[device_name](
                        device_data, self.member, self.api
                    )
                    self.devices.append(device)  # Add to device list
                    _LOGGER.debug(
                        "Successfully loaded device: %s (Serial: %s)",
                        device_name,
                        device_sn,
                    )
                else:
                    _LOGGER.error(
                        "Unsupported device found: %s (Serial: %s)",
                        device_name,
                        device_sn,
                    )

                # Mark the device as loaded to prevent duplicate API calls
                self.loaded_device_sn.add(device_sn)
                self.last_refresh_times[device_sn] = datetime.now(UTC)

            _LOGGER.debug("Final devices loaded: %s devices", len(self.devices))
        except Exception:
            _LOGGER.exception("Error while loading devices")

    async def load_member(self) -> None:
        """Load Petlibro account from the API and initialize it."""
        if self.member:
            _LOGGER.warning("Member already loaded, skipping initialization.")
            return

        try:
            member_info = await self.api.member_info()
        except Exception:
            _LOGGER.exception("Error fetching member info.")
            return

        if not member_info:
            _LOGGER.error("API returned empty member info.")
            return

        member_email = member_info.get("email")
        if not member_email:
            _LOGGER.error("API returned member info without an email: %s", member_info)
            return

        # Create the member object.
        self.member = Member(member_info, self.api)
        self.last_refresh_times[member_email] = datetime.now(UTC)
        _LOGGER.debug("Member loaded successfully: %s", member_email)

    async def _initialize_helpers(self) -> None:
        from .helpers.unit_entities import Unit_Entities  # noqa: PLC0415

        self.unit_entities = Unit_Entities(
            hass=self.hass, config_entry=self.entry, hub=self
        )

    async def refresh_data(self) -> bool:
        """Refresh all known devices and member info from the PETLIBRO API."""
        if not self.devices and not self.member:
            _LOGGER.error("No devices or member to refresh.")
            return False
        if not self.devices:
            _LOGGER.warning("No devices to refresh.")
        if not self.member:
            _LOGGER.warning("No member to refresh.")

        now = datetime.now(UTC)
        refresh_tasks, data_objects = [], []
        _LOGGER.debug("Refreshing devices and member info.")

        # Add devices if available
        if self.devices:
            for device in self.devices:
                refresh_tasks.append(self._refresh_data_if_needed(now, device=device))
                data_objects.append(device)

        # Add member if available
        if self.member:
            refresh_tasks.append(self._refresh_data_if_needed(now, member=self.member))
            data_objects.append(self.member)

        if not refresh_tasks:
            _LOGGER.warning("Nothing to refresh.")
            return False

        results = await asyncio.gather(*refresh_tasks, return_exceptions=True)

        failures = 0
        for obj, result in zip(data_objects, results):  # noqa: B905
            identifier = getattr(obj, "email", None) or getattr(
                obj, "serial", "unknown"
            )
            obj_type = "member" if isinstance(obj, Member) else "device"
            if isinstance(result, Exception):
                _LOGGER.error(
                    "Failed to refresh %s (%s): %s", obj_type, identifier, result
                )
                failures += 1
            else:
                _LOGGER.debug(
                    "Refreshed %s successfully if needed: %s", obj_type, identifier
                )

        if failures >= len(data_objects):
            msg = "All refresh operations failed."
            raise UpdateFailed(msg)

        if failures:
            _LOGGER.warning("One or more refresh operations failed.")

        _LOGGER.debug("Data refresh process finished.")
        return True

    async def _refresh_data_if_needed(
        self,
        now: datetime,
        *,
        device: Device | None = None,
        member: Member | None = None,
    ) -> None:
        """Refresh a device or member info only if enough time has passed."""
        is_member = member is not None
        obj = member if is_member else device
        obj_type_str = "member" if is_member else "device"
        identifier = obj.email if is_member else obj.serial
        last_refresh = self.last_refresh_times.get(identifier)

        force_refresh = is_member and getattr(member, "force_refresh", False)
        refresh_interval = timedelta(seconds=10)
        if is_member and not force_refresh:
            refresh_interval = timedelta(hours=6)

        if last_refresh and (now - last_refresh) < refresh_interval:
            if not force_refresh:
                _LOGGER.debug(
                    "Skipping refresh for %s (%s). Last refreshed: %s",
                    obj_type_str,
                    identifier,
                    last_refresh,
                )
                return
            _LOGGER.debug("Member was updated recently, waiting 5s..")
            await asyncio.sleep(5)

        try:
            _LOGGER.debug("Refreshing %s: %s", obj_type_str, identifier)
            await obj.refresh()
            if is_member:
                self.member.force_refresh = False
            self.last_refresh_times[identifier] = now
            _LOGGER.debug("Refresh complete for %s: %s", obj_type_str, identifier)
        except Exception:
            _LOGGER.exception("Error refreshing %s: %s", obj_type_str, identifier)
            raise

    async def get_device(self, serial: str) -> Device | None:
        """Return the device with the specified serial number."""
        device = next(
            (device for device in self.devices if device.serial == serial), None
        )
        if not device:
            _LOGGER.debug("Device with serial %s not found.", serial)
        return device

    def update_options(self, new_options: Mapping[str, Any]) -> None:
        """Update config entry options."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, **new_options},
        )
        _LOGGER.debug("Config entry options updated with: %s", new_options)

    async def async_refresh(self, force_member: bool = False) -> None:
        """
        Force a manual data refresh if enough time has passed.

        Optionally force a Member refresh.
        """
        if force_member:
            if self.member:
                self.member.force_refresh = True
            else:
                _LOGGER.warning("Member not loaded, skipping forced member refresh.")

        _LOGGER.debug("Manual data refresh triggered.")
        await self.coordinator.async_request_refresh()

    async def async_unload(self) -> bool:
        """Unload the hub and its devices."""
        _LOGGER.debug("Unloading PetLibro Hub and clearing devices.")
        self.devices.clear()  # Clears the device list
        self.last_refresh_times.clear()  # Clears refresh times as well

        # No need to stop the coordinator explicitly
        return True
