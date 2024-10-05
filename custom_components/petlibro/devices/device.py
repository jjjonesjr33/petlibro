from logging import getLogger
from typing import cast
from ..api import PetLibroAPI
from .event import Event, EVENT_UPDATE

_LOGGER = getLogger(__name__)

class Device(Event):
    def __init__(self, data: dict, api: PetLibroAPI):
        super().__init__()
        self._data: dict = {}
        self.api = api

        # Initialize the device data with the update_data method
        self.update_data(data)

    def update_data(self, data: dict) -> None:
        """Save the device info from a data dictionary."""
        try:
            # Log the update at debug level for better context
            _LOGGER.debug("Updating data with new information: %s", data)

            # Automatically update _data with any new keys, ensuring no data loss
            for key, value in data.items():
                if isinstance(value, dict):
                    # If the value is a dictionary, merge it deeply
                    self._data[key] = {**self._data.get(key, {}), **value}
                else:
                    # Otherwise, simply update or add the key
                    self._data[key] = value

            # Emit an event after updating data
            self.emit(EVENT_UPDATE)
            _LOGGER.debug("Data updated successfully: %s", self._data)

        except Exception as e:
            _LOGGER.error(f"Error updating data: {e}")
            _LOGGER.debug(f"Partial data update: {data.get('deviceSn', 'Unknown Serial')}")

    async def refresh(self):
        """Refresh the device data from the API."""
        try:
            data = {}

            # Fetch base info and real info from API
            base_info = await self.api.device_base_info(self.serial)
            real_info = await self.api.device_real_info(self.serial)

            # Update with the fetched data
            data.update(base_info)
            data.update(real_info)

            self.update_data(data)

        except Exception as e:
            _LOGGER.error(f"Failed to refresh device data: {e}")

    @property
    def serial(self) -> str:
        return cast(str, self._data.get("deviceSn"))

    @property
    def model(self) -> str:
        return cast(str, self._data.get("productIdentifier"))

    @property
    def model_name(self) -> str:
        return cast(str, self._data.get("productName"))

    @property
    def name(self) -> str:
        return cast(str, self._data.get("name"))

    @property
    def mac(self) -> str:
        return cast(str, self._data.get("mac"))

    @property
    def software_version(self) -> str:
        return cast(str, self._data.get("softwareVersion"))

    @property
    def hardware_version(self) -> str:
        return cast(str, self._data.get("hardwareVersion"))
