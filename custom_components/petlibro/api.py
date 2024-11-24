"Standalone PETLIBRO API"
## API Info
# https://api.us.petlibro.com/device/device/list
# https://api.us.petlibro.com/device/device/baseInfo
# https://api.us.petlibro.com/device/device/realInfo
# https://api.us.petlibro.com/device/setting/getAttributeSetting
# https://api.us.petlibro.com/device/data/grainStatus

from logging import getLogger
from hashlib import md5
from urllib.parse import urljoin
from typing import Any, Dict, List, TypeAlias
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryAuthFailed
from .exceptions import PetLibroAPIError, PetLibroInvalidAuth
from aiohttp import ClientSession, ClientError

import aiohttp
import uuid  # To generate unique request IDs

async def make_api_call(session, url, data):
    async with session.post(url, json=data) as response:
        return await response.json()

JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
_LOGGER = getLogger(__name__)

class PetLibroSession:
    """PetLibro AIOHTTP session"""
    
    def __init__(self, base_url: str, websession: ClientSession, email: str, password: str, region: str, token: str | None = None):
        self.base_url = base_url
        self.websession = websession
        self.token = token
        self.email = email
        self.password = password
        self.region = region
        self.headers = {
            "source": "ANDROID",
            "language": "EN",
            "timezone": "America/Chicago",
            "version": "1.3.45",
        }

    async def post(self, path: str, **kwargs: Any) -> JSON:
        """POST method for PetLibro API."""
        return await self.request("POST", path, **kwargs)

    async def post_serial(self, path: str, serial: str, **kwargs: Any) -> JSON:
        """POST request with device serial in the payload."""
        json_data = kwargs.get("json", {})
        json_data["id"] = serial  # Add serial as 'id'
        json_data["deviceSn"] = serial  # Add serial as 'deviceSn'
        kwargs["json"] = json_data
        return await self.request("POST", path, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> JSON:
        """Make a request."""
        joined_url = urljoin(self.base_url, url)
        _LOGGER.debug(f"Making {method} request to {joined_url}")

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Add default headers
        headers = self.headers.copy()
        headers.update(kwargs["headers"].copy())
        kwargs["headers"] = headers

        # Set Content-Type to JSON explicitly
        kwargs["headers"]["Content-Type"] = "application/json"

        if self.token is not None:
            kwargs["headers"]["token"] = self.token
            _LOGGER.debug(f"Using token: {self.token}")
        else:
            _LOGGER.warning("No token available for request. Attempting to log in...")

        # Send the request
        async with self.websession.request(method, joined_url, **kwargs) as resp:
            _LOGGER.debug(f"Received response status: {resp.status}")
            try:
                data = await resp.json()
            except Exception as e:
                raise PetLibroAPIError(f"Error parsing response JSON: {e}")

            _LOGGER.debug(f"Response data: {data}")

            if resp.status != 200:
                raise PetLibroAPIError(f"Request failed with status: {resp.status}")

            if data.get("code") == 1009:  # NOT_YET_LOGIN error code
                _LOGGER.warning(f"NOT_YET_LOGIN error occurred for {joined_url}. Trying re-login.")
                # Trigger a re-login and get the new token
                new_token = await self.re_login()
                kwargs["headers"]["token"] = new_token
                _LOGGER.debug(f"Retrying request with new token: {new_token}")

                # Retry the request with the new token
                async with self.websession.request(method, joined_url, **kwargs) as retry_resp:
                    retry_data = await retry_resp.json()
                    _LOGGER.debug(f"Retry response: {retry_data}")
                    return retry_data.get("data")

            if data.get("code") != 0:
                raise PetLibroAPIError(f"Code: {data.get('code')}, Message: {data.get('msg')}")

            return data.get("data")

    async def re_login(self) -> str:
        """Re-login to get a new token when the old one expires."""
        try:
            _LOGGER.debug(f"Attempting re-login with email: {self.email} and region: {self.region}")

            async with self.websession.post(
                urljoin(self.base_url, "/member/auth/login"),
                json={
                    "appId": PetLibroAPI.APPID,
                    "appSn": PetLibroAPI.APPSN,
                    "country": self.region,
                    "email": self.email,
                    "password": PetLibroAPI.hash_password(self.password),
                    "phoneBrand": "",
                    "phoneSystemVersion": "",
                    "timezone": self.headers["timezone"],
                    "thirdId": None,
                    "type": None
                },
                headers=self.headers
            ) as response:
                _LOGGER.debug(f"Re-login response status: {response.status}")

                if response.status != 200:
                    raise PetLibroAPIError(f"Failed to login, status: {response.status}")

                response_data = await response.json()
                _LOGGER.debug(f"Re-login response data: {response_data}")

                if not isinstance(response_data, dict) or "token" not in response_data.get("data", {}):
                    raise PetLibroAPIError("Token not found during login.")

                # Get the new token from response data
                new_token = response_data["data"]["token"]
                self.token = new_token  # Update the session token

                # Save the new token in the config entry
                if hasattr(self, 'api') and self.api.hass and self.api.config_entry:
                    _LOGGER.debug(f"Saving new token to config entry: {self.token}")
                    self.api.hass.config_entries.async_update_entry(
                        self.api.config_entry,
                        data={**self.api.config_entry.data, "token": self.token}
                    )

                return new_token

        except aiohttp.ClientError as e:
            _LOGGER.error(f"Re-login failed due to a client error: {e}")
            raise PetLibroAPIError(f"Client error during re-login: {e}")

        except Exception as e:
            _LOGGER.error(f"Re-login attempt failed due to an unexpected error: {e}")
            raise PetLibroAPIError(f"Unexpected error during re-login: {e}")

class PetLibroAPI:
    """PetLibro API class"""

    APPID = 1
    APPSN = "c35772530d1041699c87fe62348507a8"
    API_URLS = {
        "US": "https://api.us.petlibro.com"
    }

    def __init__(self, session: ClientSession, time_zone: str, region: str, email: str, password: str, token: str | None = None, config_entry=None, hass=None):
        """Initialize."""
        self.session = PetLibroSession(self.API_URLS[region], session, email, password, region, token)
        self.region = region
        self.time_zone = time_zone
        self.email = email  # Store email for login/re-login
        self.password = password  # Store password for login/re-login
        self.token = token
        self.config_entry = config_entry
        self.hass = hass

        # Inject the API reference into the session for token saving
        self.session.api = self

        # Load the saved token if available
        if config_entry and "token" in config_entry.data:
            self.token = config_entry.data["token"]
            _LOGGER.debug(f"Loaded saved token: {self.token}")

        self._last_api_call_times = {}  # To store last call time per device
        self._cached_responses = {}  # To store cached responses for short periods

    @staticmethod
    def hash_password(password: str) -> str:
        """Generate the password hash for the API"""
        return md5(password.encode("UTF-8")).hexdigest()

    async def login(self, email: str, password: str) -> str:
        """Login to the API and retrieve the token"""
        _LOGGER.debug("Attempting to log in with email: %s", email)
        
        try:
            # Use the request method with "POST" instead of post()
            data = await self.session.request("POST", "/member/auth/login", json={
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
                _LOGGER.error("No token found during login. Response data: %s", data)
                raise PetLibroAPIError("No token found during login.")

            self.session.token = data["token"]
            _LOGGER.debug(f"Login successful, token: {self.session.token}")
            return self.session.token

        except Exception as e:
            _LOGGER.error(f"Login failed: {e}")
            raise PetLibroAPIError(f"Login attempt failed: {e}")

    async def get_device_real_info(self, device_id: str) -> dict:
        """Fetch real-time information for a device, with caching to prevent frequent requests."""
        now = datetime.utcnow()
        last_call_time = self._last_api_call_times.get(f"{device_id}_realInfo")

        # If we made the request within the last 10 seconds, return cached response
        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping realInfo request for {device_id}, using cached response.")
            return self._cached_responses.get(f"{device_id}_realInfo", {})

        # Otherwise, make the API call and update cache
        try:
            response = await self.session.request("POST", "/device/device/realInfo", json={
                "id": device_id,
                "deviceSn": device_id
            })

            # Store the time of the API call and the cached response
            self._last_api_call_times[f"{device_id}_realInfo"] = now
            self._cached_responses[f"{device_id}_realInfo"] = response

            return response
        except Exception as e:
            _LOGGER.error(f"Error fetching realInfo for device {device_id}: {e}")
            raise PetLibroAPIError(f"Error fetching getAttributeSetting for device {device_id}: {e}")

    async def get_device_attribute_settings(self, device_id: str) -> dict:
        """Fetch real-time information for a device, with caching to prevent frequent requests."""
        now = datetime.utcnow()
        last_call_time = self._last_api_call_times.get(f"{device_id}_getAttributeSetting")

        # If we made the request within the last 10 seconds, return cached response
        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping getAttributeSetting request for {device_id}, using cached response.")
            return self._cached_responses.get(f"{device_id}_getAttributeSetting", {})

        # Otherwise, make the API call and update cache
        try:
            response = await self.session.request("POST", "/device/setting/getAttributeSetting", json={
                "id": device_id,
            })

            # Store the time of the API call and the cached response
            self._last_api_call_times[f"{device_id}_getAttributeSetting"] = now
            self._cached_responses[f"{device_id}_getAttributeSetting"] = response

            return response
        except Exception as e:
            _LOGGER.error(f"Error fetching getAttributeSetting for device {device_id}: {e}")
            raise PetLibroAPIError(f"Error fetching getAttributeSetting for device {device_id}: {e}")

    async def get_device_base_info(self, device_id: str) -> dict:
        """Fetch real-time information for a device, with caching to prevent frequent requests."""
        now = datetime.utcnow()
        last_call_time = self._last_api_call_times.get(f"{device_id}_baseInfo")

        # If we made the request within the last 10 seconds, return cached response
        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping baseInfo request for {device_id}, using cached response.")
            return self._cached_responses.get(f"{device_id}_baseInfo", {})

        # Otherwise, make the API call and update cache
        try:
            response = await self.session.request("POST", "/device/setting/baseInfo", json={
                "id": device_id,
            })

            # Store the time of the API call and the cached response
            self._last_api_call_times[f"{device_id}_baseInfo"] = now
            self._cached_responses[f"{device_id}_baseInfo"] = response

            return response
        except Exception as e:
            _LOGGER.error(f"Error fetching baseInfo for device {device_id}: {e}")
            raise PetLibroAPIError(f"Error fetching baseInfo for device {device_id}: {e}")

    async def logout(self):
        """Logout of the API and reset the token"""
        await self.session.post("/member/auth/logout")
        self.session.token = None
        _LOGGER.debug("Logout successful, token cleared.")

    async def list_devices(self) -> List[dict]:
        """
        List all account devices.

        :raises PetLibroAPIError: In case of API error
        :return: List of devices
        """
        _LOGGER.debug("Requesting list of devices")
        return await self.session.post("/device/device/list", json={})  # Ensure JSON is passed here

    async def device_base_info(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/device/baseInfo", serial)

    async def device_real_info(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/device/realInfo", serial)

    async def device_attribute_settings(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/setting/getAttributeSetting", serial)

    async def device_grain_status(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/data/grainStatus", serial)

    async def device_feeding_plan_today_new(self, serial: str) -> Dict[str, Any]:
        return await self.session.post_serial("/device/feedingPlan/todayNew", serial)

    # Support for new switch functions
    async def set_feeding_plan(self, serial: str, enable: bool):
        """Set the feeding plan on/off."""
        await self.session.post("/device/setting/updateFeedingPlanSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_child_lock(self, serial: str, enable: bool):
        """Enable or disable the child lock functionality."""
        try:
            response = await self.session.post(
                "/device/setting/updateChildLockSwitch", 
                json={"deviceSn": serial, "enable": enable}
            )

            _LOGGER.debug(f"Child lock response status: {response.status}")
            _LOGGER.debug(f"Child lock response data: {await response.text()}")

            response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set child lock for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting child lock: {err}")

    async def set_light_enable(self, serial: str, enable: bool):
        """Enable or disable the light functionality with error handling."""
        try:
            response = await self.session.post(
                "/device/setting/updateLightEnableSwitch",
                json={"deviceSn": serial, "enable": enable}
            )
            response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set light enable for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting light enable: {err}")

    async def set_light_switch(self, serial: str, enable: bool):
        """Turn the light on or off."""
        await self.session.post("/device/setting/updateLightSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_sound_enable(self, serial: str, enable: bool):
        """Enable or disable the sound functionality."""
        try:
            response = await self.session.post("/device/setting/updateSoundEnableSwitch", json={"deviceSn": serial, "enable": enable}
            )
            response.raise_for_status()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set sound enable for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting sound enable: {err}")

    async def set_desiccant_frequency(self, serial: str, replacetype: str, value: float) -> JSON:
        """Set the desiccant frequency."""
        _LOGGER.debug(f"Setting desiccant frequency: serial={serial}, value={value}, replacetype={replacetype}")
        try:
            # Generate a dynamic request ID for the manual feeding
            request_id = str(uuid.uuid4()).replace("-", "")

            response = await self.session.post("/device/device/maintenanceFrequencySetting", json={
                    "deviceSn": serial,
                    "key": replacetype,
                    "frequency": value,
                    "requestId": request_id,
                    "timeout": 5000
                },
            )
            _LOGGER.debug(f"Desiccant frequency set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set desiccant frequency for device {serial}: {e}")
            raise

    async def set_sound_switch(self, serial: str, enable: bool):
        """Turn the sound on or off."""
        await self.session.post("/device/setting/updateSoundSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_sound_level(self, serial: str, value: float):
        """Set the sound level."""
        _LOGGER.debug(f"Setting sound level: serial={serial}, value={value}")
        try:
            response = await self.session.post("/device/setting/updateVolumeSetting", json={
                "deviceSn": serial,
                "volume": value
            })
            _LOGGER.debug(f"Sound level set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set sound level for device {serial}: {e}")
            raise

    async def set_manual_feed(self, serial: str) -> JSON:
        """Trigger manual feeding for a specific device."""
        _LOGGER.debug(f"Triggering manual feeding for device with serial: {serial}")
        
        try:
            # Generate a dynamic request ID for the manual feeding
            request_id = str(uuid.uuid4()).replace("-", "")

            # Send the POST request to trigger manual feeding
            response = await self.session.post("/device/device/manualFeeding", json={
                "deviceSn": serial,
                "grainNum": 1,  # Number of grains dispensed
                "requestId": request_id  # Use dynamic request ID
            })

            # Check if response is already parsed (since response is an integer here)
            if isinstance(response, int):
                _LOGGER.debug(f"Manual feeding successful, returned code: {response}")
                return response
            
            # If response is a dictionary (JSON), handle it
            response_data = await response.json()
            _LOGGER.debug(f"Manual feeding response data: {response_data}")
            
            # Check if the response indicates success
            if response.status != 200 or response_data.get("code") != 0:
                raise PetLibroAPIError(f"Failed to trigger manual feeding: {response_data.get('msg')}")

            return response_data

        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger manual feeding for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering manual feeding: {err}")


    async def set_desiccant_reset(self, serial: str) -> JSON:
        """Trigger desiccant reset for a specific device."""
        _LOGGER.debug(f"Triggering desiccant reset for device with serial: {serial}")
        
        try:
            # Generate a dynamic request ID for the manual feeding
            request_id = str(uuid.uuid4()).replace("-", "")

            # Send the POST request to trigger manual feeding
            response = await self.session.post("/device/device/desiccantReset", json={
                "deviceSn": serial,
                "requestId": request_id,  # Use dynamic request ID
                "timeout": 5000
            })

            # Check if response is already parsed (since response is an integer here)
            if isinstance(response, int):
                _LOGGER.debug(f"Desiccant reset set successfully, returned code: {response}")
                return response
            
            # If response is a dictionary (JSON), handle it
            response_data = await response.json()
            _LOGGER.debug(f"Desiccant reset response data: {response_data}")
            
            # Check if the response indicates success
            if response.status != 200 or response_data.get("code") != 0:
                raise PetLibroAPIError(f"Failed to trigger desiccant reset: {response_data.get('msg')}")

            return response_data

        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to trigger desiccant reset for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering desiccant reset: {err}")

    async def set_manual_lid_open(self, serial: str):
        """Trigger manual lid opening for a specific device."""
        await self.session.post("/device/device/doorStateChange", json={
            "deviceSn": serial,
            "barnDoorState": True,
            "timeout": 8000
        })
    
    async def set_display_on(self, serial: str):
        """Trigger turn display on"""
        await self.session.post("/device/setting/updateDisplayMatrixSetting", json={
            "deviceSn": serial,
            "screenDisplayAgingType": 1,
            "screenDisplayStartTime": None,
            "screenDisplayEndTime": None,
            "screenDisplaySwitch": True
        })
    
    async def set_display_off(self, serial: str):
        """Trigger turn display off"""
        await self.session.post("/device/setting/updateDisplayMatrixSetting", json={
            "deviceSn": serial,
            "screenDisplayAgingType": 1,
            "screenDisplayStartTime": None,
            "screenDisplayEndTime": None,
            "screenDisplaySwitch": False
        })

    async def set_sound_on(self, serial: str):
        """Trigger turn sound on"""
        await self.session.post("/device/setting/updateSoundSetting", json={
            "deviceSn": serial,
            "soundSwitch": True,
            "soundAgingType": 1,
            "soundStartTime": None,
            "soundEndTime": None
        })
    
    async def set_sound_off(self, serial: str):
        """Trigger turn sound off"""
        await self.session.post("/device/setting/updateSoundSetting", json={
            "deviceSn": serial,
            "soundSwitch": False,
            "soundAgingType": 1,
            "soundStartTime": None,
            "soundEndTime": None
        })

## Added this to fix dupe logs
class PetLibroDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        self.api = api
        super().__init__(hass, _LOGGER, name="PetLibroData", update_interval=timedelta(minutes=1))

    async def _async_update_data(self):
        # Fetch data from the API once per update cycle
        return await self.api.fetch_device_data()        
