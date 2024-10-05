"Standalone PETLIBRO API"
from logging import getLogger
from hashlib import md5
from urllib.parse import urljoin
from typing import Any, Dict, List, TypeAlias

from aiohttp import ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed

from .exceptions import PetLibroAPIError, PetLibroInvalidAuth


JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
_LOGGER = getLogger(__name__)


class PetLibroSession:
    """PetLibro AIOHTTP session"""
    def __init__(self, base_url: str, websession: ClientSession, token : str | None = None):
        self.base_url = base_url
        self.websession = websession
        self.token = token
        self.headers = {
            "source": "ANDROID",
            "language": "EN",
            "timezone": "Europe/Paris",
            "version": "1.3.45",
        }

    async def request(self, method: str, url: str, **kwargs: Any) -> JSON:
        """Make a request."""
        joined_url = urljoin(self.base_url, url)
        _LOGGER.debug("Making %s request to %s", method, joined_url)

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Add default headers
        headers = self.headers.copy()
        headers.update(kwargs["headers"].copy())
        kwargs["headers"] = headers

        if self.token is not None:
            kwargs["headers"]["token"] = self.token

        # The API require an empty JSON
        if "json" not in kwargs:
            kwargs["json"] = {}

        async with self.websession.request(method, joined_url, **kwargs) as resp:
            if resp.status != 200:
                raise PetLibroAPIError(resp.content)

            data = await resp.json()

            _LOGGER.debug(
                "Received %s response from %s: %s", resp.status, joined_url, data
            )

            if not data:
                raise PetLibroAPIError("No JSON data")

            if data.get("code") == 1102:
                raise PetLibroInvalidAuth()

            if data.get("code") == 1009:
                raise ConfigEntryAuthFailed(data.get("msg"))

            # Catch all other non 0 code
            if data.get("code") != 0:
                raise PetLibroAPIError(f"Code: {data.get('code')}, Message: {data.get('msg')}")

            return data.get("data")

    async def post(self, path: str, **kwargs: Any) -> JSON:
        """Post on PetLibro API"""
        return await self.request("POST", path, **kwargs)

    async def post_serial(self, path: str, serial: str, **kwargs: Any) -> JSON:
        """Post on PetLibro API with device serial"""
        return await self.request("POST", path, json={
                "id": serial
            }, **kwargs)


class PetLibroAPI:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    APPID = 1
    APPSN = "c35772530d1041699c87fe62348507a8"
    API_URLS = {
        "US": "https://api.us.petlibro.com"
    }

    def __init__(self, session: ClientSession, time_zone: str, region: str,
                 token: str | None = None) -> None:
        """Initialize."""
        self.session = PetLibroSession(self.API_URLS[region], session, token)
        self.region = region
        self.time_zone = time_zone

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Generate the password hash for the API

        :param password: The password
        :return: Hashed password
        """
        return md5(password.encode("UTF-8")).hexdigest()

    async def login(self, email: str, password: str) -> str:
        """
        Login to the API

        :param email: The account email
        :param password_hash: The account password hash
        :raises PetLibroAPIError: In case of API error
        """
        data = await self.session.post("/member/auth/login", json={
            "appId": self.APPID,
            "appSn": self.APPSN,
            "country": self.region,
            "email": email,
            "password": self.hash_password(password),
            "phoneBrand": "",
            "phoneSystemVersion": "",
            "timezone": self.time_zone,
            "thirdId": None,
            "type": None
        })

        if not isinstance(data, dict) or "token" not in data or not isinstance(data["token"], str):
            raise PetLibroAPIError("No token")

        return data["token"]

    async def logout(self):
        """
        Logout of the API
        """
        await self.session.post("/member/auth/logout")
        self.session.token = None

    async def list_devices(self) -> List[dict]:
        """
        List all account devices

        :raises PetLibroAPIError: In case of API error
        :return: List of devices
        """
        return await self.session.post("/device/device/list")  # type: ignore

    async def device_base_info(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/device/baseInfo", serial)  # type: ignore

    async def device_real_info(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/device/realInfo", serial)  # type: ignore

    async def device_grain_status(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/data/grainStatus", serial)  # type: ignore

    async def device_feeding_plan_today_new(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/feedingPlan/todayNew", serial)  # type: ignore

    # Support for new switch functions

    async def set_feeding_plan(self, serial: str, enable: bool):
        """Set the feeding plan on/off"""
        await self.session.post("/device/setting/updateFeedingPlanSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_child_lock(self, serial: str, enable: bool):
        """Enable or disable the child lock functionality."""
        try:
            response = await self.session.post(
                "/device/setting/updateChildLockSwitch", 
                json={
                    "deviceSn": serial,
                    "enable": enable
                }
            )
            response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set child lock for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting child lock: {err}")

    async def set_light_enable(self, serial: str, enable: bool):
        """Enable or disable the light functionality with error handling."""
        try:
            response = await self.session.post(
                "/device/setting/updateLightEnableSwitch",
                json={
                    "deviceSn": serial,
                    "enable": enable
                }
            )
            response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set light enable for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting light enable: {err}")

    async def set_light_switch(self, serial: str, enable: bool):
        """Turn the light on or off"""
        await self.session.post("/device/setting/updateLightSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_sound_enable(self, serial: str, enable: bool):
        """Enable or disable the sound functionality."""
        try:
            response = await self.session.post(
                "/device/setting/updateSoundEnableSwitch", 
                json={
                    "deviceSn": serial,
                    "enable": enable
                }
            )
            response.raise_for_status()  # Raises an HTTPError if the status is 4xx or 5xx
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set sound enable for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting sound enable: {err}")

    async def set_sound_switch(self, serial: str, enable: bool):
        """Turn the sound on or off"""
        await self.session.post("/device/setting/updateSoundSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_device_manual_feeding(self, serial: str):
        return await self.session.post("/device/device/manualFeeding", json={
            "deviceSn": serial,
            "grainNum": 1,  # try and make this dynamic. add a number entity for the amount perhaps.
            "requestId": "50ef5fdf9c8146bdba873934b1041200",  # replace with real hashed md5 request id. we can probably just generate a random one each time.
        })
