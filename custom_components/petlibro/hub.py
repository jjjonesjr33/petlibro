import asyncio

from logging import getLogger
from collections.abc import Mapping
import sys
from typing import Any
from datetime import datetime, timedelta
from .const import UPDATE_INTERVAL_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_REGION, CONF_API_TOKEN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.device_registry import async_get as async_get_device_register
from homeassistant.util.dt import utcnow
from .api import PetLibroAPI  # Use a relative import if inside the same package
from .const import CONF_EMAIL, CONF_PASSWORD, IntegrationSetting
from .devices import Device, product_name_map
from .member import Member
from .pets import Pet
from .helpers import set_missing_config_options

_LOGGER = getLogger(__name__)

class PetLibroHub:
    """A PetLibro hub wrapper class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the PetLibro Hub."""
        self.hass = hass
        self.entry = config_entry
        self._data = self.entry.data
        self.devices: dict[str, Device] = {}
        self.pets: dict[str, Pet] = {}
        self.last_refresh_times = {}  # Track the last refresh time for the member, each pet & each device
        self._last_online_status = {}  # Store online status per device

        # Fetch email, password, and region from entry.data
        email = self.entry.data.get(CONF_EMAIL)
        password = self.entry.data.get(CONF_PASSWORD)
        region = self.entry.data.get(CONF_REGION)

        # Check if the required information is provided
        if not email:
            _LOGGER.error("Email is missing in the configuration entry.")
            raise ValueError("Email is required to initialize PetLibroAPI.")
        if not password:
            _LOGGER.error("Password is missing in the configuration entry.")
            raise ValueError("Password is required to initialize PetLibroAPI.")
        if not region:
            _LOGGER.error("Region is missing in the configuration entry.")
            raise ValueError("Region is required to initialize PetLibroAPI.")

        _LOGGER.debug(f"Initializing PetLibroAPI with email: {email}, region: {region}")

        # Initialize the PetLibro API instance
        self.api = PetLibroAPI(
            async_get_clientsession(hass),
            hass.config.time_zone,
            region,
            email,
            password,
            self.entry.data.get(CONF_API_TOKEN)
        )

        # Setup DataUpdateCoordinator to periodically refresh device data
        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="petlibro_data",
            update_method=self.refresh_data,  # Calls the refresh_data method
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),  # Use defined interval
        )

        self.member = Member(self.api)
        set_missing_config_options(self)
        
        self.device_register = async_get_device_register(self.hass)

    async def load_devices(self) -> None:
        """Load devices from the API and initialize them."""
        try:
            device_list = await self.api.list_devices()
            _LOGGER.debug(f"Fetched {len(device_list)} devices from the API.")

            if not device_list:
                _LOGGER.warning("No devices found in the API response.")
                return  # Early return if no devices found

            for device_data in device_list:
                device_sn = device_data.get("deviceSn", "unknown")
                device_name = device_data.get("productName", "unknown")
                _LOGGER.debug(f"Processing device: {device_name} (Serial: {device_sn})")

                # Check if the device is already loaded
                if device_sn in self.devices_helper.loaded_device_sn:
                    _LOGGER.debug(f"Device {device_sn} is already loaded, skipping further initialization.")
                    continue

                # Get pet ids bound to this device if it's shared and shared pets are enabled
                if (
                    self.entry.options.get(IntegrationSetting.ENABLE_SHARED_PETS)
                    and device_data.get("shareId") 
                    and device_sn != "unknown"
                ):
                    bound_pets = await self.api.device_get_bound_pets(device_sn)
                    self.pets_helper.shared_pet_ids.update(
                        pet_id
                        for pet in bound_pets
                        if (pet_id := pet.get("id"))
                        and (member_id := pet.get("memberId"))
                        and member_id != self.member.id
                    )
                    device_data.update({"boundPets": bound_pets})

                # Create a new device and add it without calling refresh immediately
                if device_name in product_name_map:
                    _LOGGER.debug(f"Loading new device: {device_name} (Serial: {device_sn})")
                    device = product_name_map[device_name](device_data, self)
                    self.devices[device_sn] = device # Add to device dict
                    _LOGGER.debug(f"Successfully loaded device: {device_name} (Serial: {device_sn})")
                else:
                    _LOGGER.error(f"Unsupported device found: {device_name} (Serial: {device_sn})")

                # Mark the device as loaded to prevent duplicate API calls
                self.devices_helper.loaded_device_sn.add(device_sn)
                self.last_refresh_times[device_sn] = utcnow()  # Set the last refresh time to now

            await self.devices_helper.remove_device_entries(
                self.devices_helper.loaded_device_sn, keep=True
            )

            _LOGGER.debug(f"Final devices loaded: {len(self.devices)} devices")
        except Exception as ex:
            _LOGGER.error(f"Error while loading devices: {ex}", exc_info=True)

    async def load_member(self) -> None:
        """Load Petlibro account from the API and initialize it."""

        if self.member._data:
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

        # Populate the member object data.
        self.member.update_data(member_info)
        self.last_refresh_times[member_email] = utcnow()
        _LOGGER.debug("Member loaded successfully: %s", member_email)

    async def load_pets(self) -> None:
        """Load pets from the API and initialize them."""
        try:
            response = await self.api.pets.get_list()
            pet_list: list[dict] = response.get("petList", [])

            #TODO seperate shared pets into a different try so owned ones can still get loaded
            if self.entry.options.get(IntegrationSetting.ENABLE_SHARED_PETS):
                for pet_data in pet_list:
                    self.pets_helper.shared_pet_ids.discard(pet_data.get("id"))
            
                for pet_id in self.pets_helper.shared_pet_ids:
                    pet_list.append(await self.api.pets.get_details(pet_id))
        
            _LOGGER.debug(f"Fetched {len(pet_list)} pets from the API.")
        except Exception:
            _LOGGER.exception("Error fetching pet info.")
            return

        # Get shared pets if set to do so.
        if self.entry.options.get(
            IntegrationSetting.ENABLE_SHARED_PETS,
            IntegrationSetting.ENABLE_SHARED_PETS.default,
        ):
            try:
                for pet_id in self.pets_helper.shared_pet_ids:
                    if pet_data := await self.api.pets.get_details(pet_id):
                        pet_list.append(pet_data)
            except Exception:
                _LOGGER.error("Error fetching shared pet info.")

        if not pet_list:
            _LOGGER.warning("No pets found in the API response.")
            return  # Early return if no pets found

        for pet_data in pet_list:
            pet_name = pet_data.get("name")
            pet_id = pet_data.get("id")
            _LOGGER.debug(f"Processing pet: {pet_name}")

            # Check if the pet is already loaded
            if pet_id in self.pets_helper.loaded_pet_ids:
                _LOGGER.debug(
                    f"Pet {pet_name} is already loaded, skipping further initialization."
                )
                continue

            # Create a new pet and add it without calling refresh immediately
            _LOGGER.debug(f"Loading new pet: {pet_name}")
            pet = Pet(pet_data, self)
            self.pets.update({str(pet_id): pet})  # Add to pet dict
            _LOGGER.debug(f"Successfully loaded pet: {pet_name}")

            # Mark the pet as loaded to prevent duplicate API calls
            self.pets_helper.loaded_pet_ids.add(pet_id)
            self.last_refresh_times[str(pet_id)] = utcnow() # Set the last refresh time to now
            _LOGGER.debug(f"Final pets loaded: {len(self.pets)} pets")

        await self.pets_helper.remove_pet_entries(
            self.pets_helper.loaded_pet_ids, keep=True
        )

    async def _initialize_helpers(self) -> None:
        """Initialise helper classes."""
        if "Unit_Entities" not in sys.modules:
            from .helpers.unit_entities import Unit_Entities
        if "PetsHelper" not in sys.modules:
            from .helpers.pets import PetsHelper
        if "DevicesHelper" not in sys.modules:
            from .helpers.devices import DevicesHelper

        self.unit_entities = Unit_Entities(hass=self.hass, config_entry=self.entry, hub=self)
        self.pets_helper = PetsHelper(hass=self.hass, config_entry=self.entry, hub=self)
        self.devices_helper = DevicesHelper(hass=self.hass, config_entry=self.entry, hub=self)

    async def refresh_data(self) -> bool:
        """Refresh all known devices, member and pets info from the PETLIBRO API."""

        if not self.devices and not self.member and not self.pets:
            _LOGGER.error("No devices, member, or pets to refresh.")
            return False
        if not self.devices:
            _LOGGER.warning("No devices to refresh.")
        if not self.member:
            _LOGGER.warning("No member to refresh.")
        if not self.pets:
            _LOGGER.warning("No pets to refresh.")

        now = utcnow()
        refresh_tasks, data_objects = [], []
        _LOGGER.debug("Refreshing devices, member and pets info.")

        # Add devices if available
        if self.devices:
            for device in self.devices.values():
                refresh_tasks.append(self._refresh_data_if_needed(now, device))
                data_objects.append(device)

        # Add member if available
        if self.member:
            refresh_tasks.append(self._refresh_data_if_needed(now, self.member))
            data_objects.append(self.member)

        # Add pets if available
        if self.pets:
            for pet in self.pets.values():
                refresh_tasks.append(self._refresh_data_if_needed(now, pet))
                data_objects.append(pet)

        if not refresh_tasks:
            _LOGGER.warning("Nothing to refresh.")
            return False

        results = await asyncio.gather(*refresh_tasks, return_exceptions=True)

        failures = 0
        for obj, result in zip(data_objects, results):
            identifier = (
                getattr(obj, "email", None)  # Member
                or getattr(obj, "serial", None)  # Device
                or getattr(obj, "name", "unknown")  # Pet
            )
            obj_type = (
                "member"
                if isinstance(obj, Member)
                else "pet"
                if isinstance(obj, Pet)
                else "device"
            )
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
            raise UpdateFailed("All refresh operations failed.")

        if failures:
            _LOGGER.warning("One or more refresh operations failed.")

        _LOGGER.debug("Data refresh process finished.")
        return True

    async def _refresh_data_if_needed(
        self,
        now: datetime,
        refresh_obj: Device | Member | Pet,
    ) -> None:
        """Refresh a device, pet or member info only if enough time has passed."""

        force_refresh = False
        is_member = False
        if isinstance(refresh_obj, Member):
            is_member = True
            obj_type_str = "member"
            identifier = refresh_obj.email
            force_refresh = getattr(refresh_obj, "force_refresh", False)
        elif isinstance(refresh_obj, Device):
            obj_type_str = "device"
            identifier = refresh_obj.serial
        elif isinstance(refresh_obj, Pet):
            obj_type_str = "pet"
            identifier = refresh_obj.id
        else:
            _LOGGER.error(
                "Error refreshing %s: Object is not an instance of Member, Device or Pet",
                refresh_obj,
            )
            raise

        last_refresh = self.last_refresh_times.get(identifier)
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
            await refresh_obj.refresh()
            if is_member:
                self.member.force_refresh = False
            else:
                if not refresh_obj.device_id:
                    refresh_obj.set_device_id()
                if not refresh_obj.saved_to_options:
                    refresh_obj.save_to_options()
            self.last_refresh_times[identifier] = now
            _LOGGER.debug("Refresh complete for %s: %s", obj_type_str, identifier)
        except Exception:
            _LOGGER.exception("Error refreshing %s: %s", obj_type_str, identifier)
            raise

    def get_device(self, serial: str) -> Device | None:
        """Return the device with the specified serial number."""
        device = self.devices.get(serial)
        if not device:
            _LOGGER.debug("Device with serial %s not found.", serial)
        return device

    def get_pet(self, id: int | str) -> Pet | None:
        """Return the pet with the specified pet id."""
        pet = self.pets.get(str(id))
        if not pet:
            _LOGGER.debug("Pet with id %s not found.", id)
        return pet

    def update_options(self, new_options: Mapping[str, Any]) -> None:
        """Update config entry options."""
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={**self.entry.options, **new_options},
        )
        _LOGGER.debug(f"Config entry options updated with: {new_options}")

    async def async_refresh(self, force_member: bool = False) -> None:
        """Force a manual data refresh if enough time has passed.

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
        self.pets.clear()  # Clears the pet list
        self.last_refresh_times.clear()  # Clears refresh times as well
        
        # No need to stop the coordinator explicitly
        return True
