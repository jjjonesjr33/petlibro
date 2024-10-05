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

        self.update_data(data)

    def update_data(self, data: dict) -> None:
        """Save the device info from a data dictionary."""
        _LOGGER.error("Updating data with: %s", data)
        self._data.update(data)
        self.emit(EVENT_UPDATE)
        _LOGGER.error("Data after update: %s", self._data)

    async def refresh(self):
        """Refresh the device data from the API."""
        data = {}
        data.update(await self.api.device_base_info(self.serial))
        data.update(await self.api.device_real_info(self.serial))
        self.update_data(data)

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
