"Standalone PETLIBRO API with enhanced reliability features"
# API Info
# https://api.us.petlibro.com/device/device/list
# https://api.us.petlibro.com/device/device/baseInfo
# https://api.us.petlibro.com/device/device/realInfo
# https://api.us.petlibro.com/device/setting/getAttributeSetting
# https://api.us.petlibro.com/device/data/grainStatus

from logging import getLogger
from hashlib import md5
import asyncio
import time
import random
from urllib.parse import urljoin
from typing import Any, Dict, List, TypeAlias, Optional, Tuple
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryAuthFailed
from .exceptions import PetLibroAPIError, PetLibroInvalidAuth, PetLibroConnectionError
from aiohttp import ClientSession, ClientError, ClientResponseError, ClientConnectorError, ServerTimeoutError

from .const import DEFAULT_MAX_BACKOFF_TIME
from .state_cache import PetLibroStateCache

import aiohttp
import uuid  # To generate unique request IDs

async def make_api_call(session, url, data):
    async with session.post(url, json=data) as response:
        return await response.json()

JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
_LOGGER = getLogger(__name__)

class PetLibroErrorCategory:
    """Error categories for PetLibro API."""
    NETWORK = "network"
    AUTH = "auth"
    SERVER = "server"
    CLIENT = "client"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"

class PetLibroSession:
    """Enhanced PetLibro AIOHTTP session with retry logic."""
    
    def __init__(
        self, 
        hass,
        base_url: str, 
        websession: ClientSession, 
        email: str, 
        password: str, 
        region: str, 
        token: str | None = None,
        cache: Optional[PetLibroStateCache] = None,
        max_retries: int = 3, 
        request_timeout: int = 10
    ):
        """Initialize the PetLibro session.
        
        Args:
            base_url: The base URL for the PetLibro API
            websession: The aiohttp client session
            email: User email for authentication
            password: User password for authentication
            region: User region for API selection
            token: Optional authentication token
            cache: Optional state cache reference for fallback data
            max_retries: Maximum number of retry attempts for failed requests
            request_timeout: Default timeout for requests in seconds
        """
        self.hass = hass
        self.base_url = base_url
        self.websession = websession
        self.token = token
        self.email = email
        self.password = password
        
        # New parameters
        self.cache = cache  # State cache reference
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.connection_state = "unknown"  # Track connection state
        self._connection_errors = 0  # Count consecutive connection errors
        self._last_successful_request = 0  # Timestamp of last successful API call
        self._token_last_refresh = 0  # Timestamp of last token refresh
        self._token_refresh_lock = asyncio.Lock()  # Lock for token refresh
        
        # Region and headers
        self.region = region
        self.headers = {
            "source": "ANDROID",
            "language": "EN",
            "timezone": "America/Chicago",
            "version": "1.3.45",
        }

    def update_connection_state(self, success: bool = True, error: Optional[Exception] = None, device_name: Optional[str] = None) -> None:
        """Update connection state based on API call results.
        
        Args:
            success: Whether the API call was successful
            error: The exception if the call failed
            device_name: Optional device name for device-specific connection events
        """
        previous_state = self.connection_state
        current_time = time.time()
        
        if success:
            self._connection_errors = 0
            self._last_successful_request = current_time
            self.connection_state = "online"
        else:
            self._connection_errors += 1
            
            # Determine state based on consecutive errors and time since last success
            if self._connection_errors > 5:
                time_since_success = current_time - self._last_successful_request
                if time_since_success > 300:  # 5 minutes
                    self.connection_state = "offline"
                else:
                    self.connection_state = "degraded"
            
            # Log the error for debugging
            if error:
                _LOGGER.debug(f"API error: {error}, connection state: {self.connection_state}")
                
        # Fire event if connection state changed
        if previous_state != self.connection_state and hasattr(self, 'hass'):
            self.hass.bus.async_fire(
                "petlibro_connection_change",
                {
                    "state": self.connection_state,
                    "previous_state": previous_state,
                    "device_name": device_name
                }
            )

    def categorize_error(self, error: Exception) -> str:
        """Categorize an error based on its type.
        
        Args:
            error: The exception to categorize
            
        Returns:
            The error category
        """
        if isinstance(error, PetLibroInvalidAuth):
            return PetLibroErrorCategory.AUTH
        elif isinstance(error, ServerTimeoutError) or isinstance(error, asyncio.TimeoutError):
            return PetLibroErrorCategory.TIMEOUT
        elif isinstance(error, ClientConnectorError):
            return PetLibroErrorCategory.NETWORK
        elif isinstance(error, ClientResponseError):
            if 400 <= error.status < 500:
                return PetLibroErrorCategory.CLIENT
            elif 500 <= error.status < 600:
                return PetLibroErrorCategory.SERVER
        
        # Default to network for other ClientError types
        if isinstance(error, ClientError):
            return PetLibroErrorCategory.NETWORK
            
        return PetLibroErrorCategory.UNKNOWN

    async def request_with_retry(self, method: str, url: str, retry_auth: bool = True, 
                                **kwargs: Any) -> JSON:
        """Make a request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: The URL path
            retry_auth: Whether to retry authentication failures
            **kwargs: Additional arguments for the request
            
        Returns:
            The API response data
            
        Raises:
            PetLibroAPIError: If the request fails after all retries
            PetLibroInvalidAuth: If authentication fails
        """
        retry_count = 0
        last_exception = None
        
        # Set default timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.request_timeout
        
        while retry_count <= self.max_retries:
            try:
                # Make the request
                response = await self.request(method, url, **kwargs)
                
                # If successful, update connection state and return response
                self.update_connection_state(success=True)
                return response
                
            except PetLibroInvalidAuth as auth_error:
                # Handle authentication errors differently
                if retry_auth and retry_count < self.max_retries:
                    try:
                        _LOGGER.debug("Authentication error, attempting to refresh token")
                        new_token = await self.re_login()
                        if 'headers' in kwargs:
                            kwargs['headers']['token'] = new_token
                        # Try again with new token
                        retry_count += 1
                        continue
                    except Exception as refresh_error:
                        _LOGGER.error(f"Token refresh failed: {refresh_error}")
                        self.update_connection_state(success=False, error=refresh_error)
                        raise PetLibroInvalidAuth(f"Authentication failed: {auth_error}")
                else:
                    self.update_connection_state(success=False, error=auth_error)
                    raise
                    
            except Exception as error:
                # Categorize error for better handling
                error_category = self.categorize_error(error)
                last_exception = error
                
                if retry_count < self.max_retries:
                    # Implement exponential backoff with jitter
                    backoff_time = min(2 ** retry_count + random.uniform(0, 1), DEFAULT_MAX_BACKOFF_TIME)
                    _LOGGER.debug(f"Request failed ({error_category}), retrying in {backoff_time:.2f}s: {error}")
                    await asyncio.sleep(backoff_time)
                    retry_count += 1
                else:
                    # Update connection state with failure
                    self.update_connection_state(success=False, error=error)
                    
                    # Convert to appropriate PetLibro error type
                    if error_category == PetLibroErrorCategory.NETWORK:
                        raise PetLibroConnectionError(f"Network error after {retry_count} retries: {error}")
                    else:
                        raise PetLibroAPIError(f"API error after {retry_count} retries: {error}")
        
        raise PetLibroAPIError(f"Request failed after {retry_count} retries: {last_exception}")

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

    async def get(self, path: str, params: dict = None, **kwargs: Any) -> JSON:
        """GET method for the PetLibro API."""
        return await self.request("GET", path, params=params, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> JSON:
        """Make a request.
        
        This is the base request method that handles token management and response parsing.
        For retry logic, use request_with_retry instead.
        """
        joined_url = urljoin(self.base_url, url)
        _LOGGER.debug(f"Making {method} request to {joined_url}")

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        # Add default headers and set timeout
        headers = self.headers.copy()
        headers.update(kwargs["headers"].copy())
        kwargs["headers"] = headers
        
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.request_timeout

        # Set Content-Type to JSON explicitly
        kwargs["headers"]["Content-Type"] = "application/json"

        if self.token is not None:
            kwargs["headers"]["token"] = self.token
        else:
            _LOGGER.warning("No token available for request. Attempting to log in...")

        try:
            # Send the request
            async with self.websession.request(method, joined_url, **kwargs) as resp:
                _LOGGER.debug(f"Received response status: {resp.status}")
                try:
                    data = await resp.json()
                except Exception as e:
                    raise PetLibroAPIError(f"Error parsing response JSON: {e}")

                if resp.status != 200:
                    resp.raise_for_status()  # This will raise ClientResponseError

                if data.get("code") == 1009:  # NOT_YET_LOGIN error code
                    _LOGGER.debug(f"NOT_YET_LOGIN error occurred for {joined_url}. Trying re-login.")
                    # Trigger a re-login and get the new token
                    new_token = await self.re_login()
                    kwargs["headers"]["token"] = new_token
                    _LOGGER.debug(f"Retrying request with new token: {new_token}")

                    # Retry the request with the new token
                    async with self.websession.request(method, joined_url, **kwargs) as retry_resp:
                        retry_resp.raise_for_status()
                        retry_data = await retry_resp.json()
                        _LOGGER.debug(f"Retry response: {retry_data}")
                        return retry_data.get("data")

                if data.get("code") != 0:
                    raise PetLibroAPIError(f"Code: {data.get('code')}, Message: {data.get('msg')}")

                return data.get("data")
                
        except ClientResponseError as e:
            raise PetLibroAPIError(f"Request failed with status {e.status}: {e.message}")

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
                    headers=self.headers,
                    timeout=self.request_timeout
            ) as response:
                response.raise_for_status()

                response_data = await response.json()
                _LOGGER.debug(f"Re-login response data: {response_data}")

                if response_data.get("code") != 0:
                    raise PetLibroInvalidAuth(f"Login failed: {response_data.get('msg')}")

                if not isinstance(response_data, dict) or "token" not in response_data.get("data", {}):
                    raise PetLibroAPIError("Token not found during login.")

                # Get the new token from response data
                new_token = response_data["data"]["token"]
                self.token = new_token  # Update the session token
                self._token_last_refresh = time.time()

                # Save the new token in the config entry
                if hasattr(self, 'api') and self.api.hass and self.api.config_entry:
                    _LOGGER.debug(f"Saving new token to config entry: {self.token}")
                    self.api.hass.config_entries.async_update_entry(
                        self.api.config_entry,
                        data={**self.api.config_entry.data, "token": self.token}
                    )
                
                # Update connection state to online
                self.update_connection_state(success=True)

                return new_token

        except ClientResponseError as e:
            if 400 <= e.status < 500:
                _LOGGER.error(f"Authentication failed: {e}")
                raise PetLibroInvalidAuth(f"Authentication failed: {e}")
            _LOGGER.error(f"Re-login failed due to server error: {e}")
            raise PetLibroAPIError(f"Server error during re-login: {e}")
            
        except ClientError as e:
            _LOGGER.error(f"Re-login failed due to a client error: {e}")
            raise PetLibroConnectionError(f"Network error during re-login: {e}")

        except Exception as e:
            _LOGGER.error(f"Re-login attempt failed due to an unexpected error: {e}")
            raise PetLibroAPIError(f"Unexpected error during re-login: {e}")

class PetLibroAPI:
    """Enhanced PetLibro API class with retry logic and fallback"""

    APPID = 1
    APPSN = "c35772530d1041699c87fe62348507a8"
    API_URLS = {
        "US": "https://api.us.petlibro.com"
    }

    def __init__(
        self, 
        session: ClientSession, 
        time_zone: str, 
        region: str, 
        email: str, 
        password: str, 
        token: str | None = None, 
        config_entry=None, 
        hass=None, 
        cache: Optional[PetLibroStateCache] = None
    ):
        """Initialize."""
        self.session = PetLibroSession(hass, self.API_URLS[region], session, email, password, region, token, cache)
        self.region = region
        self.time_zone = time_zone
        self.email = email  # Store email for login/re-login
        self.password = password  # Store password for login/re-login
        self.token = token
        self.cache = cache  # Store cache reference
        self.config_entry = config_entry
        self.hass = hass

        # Inject the API reference into the session for token saving
        self.session.api = self

        if config_entry and "token" in config_entry.data:
            self.token = config_entry.data["token"]
            _LOGGER.debug(f"Loaded saved token: {self.token}")

        self._last_api_call_times = {}  # To store last call time per device
        self._cached_responses = {}  # To store cached responses for short periods

    @property
    def connection_state(self) -> str:
        """Get the current connection state."""
        return self.session.connection_state

    @staticmethod
    def hash_password(password: str) -> str:
        """Generate the password hash for the API"""
        return md5(password.encode("UTF-8")).hexdigest()

    async def get_cached_device_data(self, device_id: str, attribute: str) -> Tuple[Any, bool]:
        """Get cached device data with freshness info.
        
        Args:
            device_id: The device ID
            attribute: The attribute name
            
        Returns:
            A tuple of (attribute_value, is_fresh) or (None, False) if no cache
        """
        if self.cache:
            return self.cache.get_attribute(device_id, attribute, max_age_seconds=300)
        return None, False

    async def update_device_cache(self, device_id: str, data: Dict[str, Any]) -> None:
        """Update device data in cache.
        
        Args:
            device_id: The device ID
            data: The data to cache
        """
        if self.cache:
            self.cache.update_device_state(device_id, data)

    async def login(self, email: str, password: str) -> str:
        """Login to the API and retrieve the token"""
        _LOGGER.debug("Attempting to log in with email: %s", email)
        
        try:
            # Use re_login to ensure consistent logic
            return await self.session.re_login()

        except PetLibroInvalidAuth:
            _LOGGER.error("Invalid credentials during login")
            raise
            
        except PetLibroAPIError as e:
            _LOGGER.error(f"API error during login: {e}")
            raise

    async def get_device_real_info(self, device_id: str) -> dict:
        """Fetch real-time information for a device, with caching to prevent frequent requests."""
        now = datetime.utcnow()
        last_call_time = self._last_api_call_times.get(f"{device_id}_realInfo")

        # If we made the request within the last 10 seconds, return memory-cached response
        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping realInfo request for {device_id}, using cached response.")
            return self._cached_responses.get(f"{device_id}_realInfo", {})

        # Otherwise, make the API call with retry logic
        try:
            response = await self.session.request_with_retry("POST", "/device/device/realInfo", json={
                "id": device_id,
                "deviceSn": device_id
            })
            
            # Store the time of the API call and the cached response
            self._last_api_call_times[f"{device_id}_realInfo"] = now
            self._cached_responses[f"{device_id}_realInfo"] = response
            
            # Update persistent cache
            if self.cache:
                await self.update_device_cache(device_id, response)

            return response
        except (PetLibroConnectionError, PetLibroAPIError) as e:
            _LOGGER.warning(f"Error fetching realInfo for device {device_id}: {e}")
            
            # Try to get from cache
            if self.cache:
                cached_data = self.cache.get_device_state(device_id)
                if cached_data:
                    _LOGGER.info(f"Using cached data for device {device_id} due to API error")
                    return cached_data
            
            # If no cache or empty cache, re-raise
            raise

    async def get_device_attribute_settings(self, device_id: str) -> dict:
        """Fetch attribute settings for a device, with caching to prevent frequent requests."""
        now = datetime.utcnow()
        last_call_time = self._last_api_call_times.get(f"{device_id}_getAttributeSetting")

        # If we made the request within the last 10 seconds, return memory-cached response
        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping getAttributeSetting request for {device_id}, using cached response.")
            return self._cached_responses.get(f"{device_id}_getAttributeSetting", {})

        # Otherwise, make the API call with retry logic
        try:
            response = await self.session.request_with_retry("POST", "/device/setting/getAttributeSetting", json={
                "id": device_id,
            })
            
            # Store the time of the API call and the cached response
            self._last_api_call_times[f"{device_id}_getAttributeSetting"] = now
            self._cached_responses[f"{device_id}_getAttributeSetting"] = response
            
            # Update persistent cache
            if self.cache:
                await self.update_device_cache(device_id, response)

            return response
        except (PetLibroConnectionError, PetLibroAPIError) as e:
            _LOGGER.warning(f"Error fetching getAttributeSetting for device {device_id}: {e}")
            
            # Try to get from cache
            if self.cache:
                cached_data = self.cache.get_device_state(device_id)
                if cached_data:
                    _LOGGER.info(f"Using cached data for device {device_id} due to API error")
                    return cached_data
            
            # If no cache or empty cache, re-raise
            raise

    async def get_device_base_info(self, device_id: str) -> dict:
        """Fetch real-time information for a device, with caching to prevent frequent requests."""
        now = datetime.utcnow()
        last_call_time = self._last_api_call_times.get(f"{device_id}_baseInfo")

        # If we made the request within the last 10 seconds, return memory-cached response
        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Skipping baseInfo request for {device_id}, using cached response.")
            return self._cached_responses.get(f"{device_id}_baseInfo", {})

        # Otherwise, make the API call with retry logic
        try:
            response = await self.session.request_with_retry("POST", "/device/setting/baseInfo", json={
                "id": device_id,
            })

            # Store the time of the API call and the cached response
            self._last_api_call_times[f"{device_id}_baseInfo"] = now
            self._cached_responses[f"{device_id}_baseInfo"] = response
            
            # Update persistent cache
            if self.cache:
                await self.update_device_cache(device_id, response)

            return response
        except (PetLibroConnectionError, PetLibroAPIError) as e:
            _LOGGER.warning(f"Error fetching baseInfo for device {device_id}: {e}")
            
            # Try to get from cache
            if self.cache:
                cached_data = self.cache.get_device_state(device_id)
                if cached_data:
                    _LOGGER.info(f"Using cached data for device {device_id} due to API error")
                    return cached_data
            
            # If no cache or empty cache, re-raise
            raise

    async def fetch_device_data_parallel(self, device_id: str) -> dict:
        """Fetch all device data in parallel for better performance.
        
        Args:
            device_id: The device ID
            
        Returns:
            Combined device data from multiple API calls
        """
        tasks = [
            self.device_base_info(device_id),
            self.device_real_info(device_id),
            self.device_attribute_settings(device_id)
        ]
        
        # Execute API calls in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        data = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                _LOGGER.warning(f"API call {i} failed: {result}")
            else:
                data.update(result)
        
        # Cache the combined data
        if self.cache and data:
            await self.update_device_cache(device_id, data)
        
        return data

    async def get_default_matrix(self, device_sn: str) -> dict:
        """
        Fetch the default matrix for a device using a GET request.
        
        :param device_sn: The serial number of the device.
        :return: The default matrix data.
        """
        # Check cache for recently fetched data
        now = datetime.utcnow()
        cache_key = f"{device_sn}_getDefaultMatrix"
        last_call_time = self._last_api_call_times.get(cache_key)

        if last_call_time and (now - last_call_time) < timedelta(seconds=10):
            _LOGGER.debug(f"Using cached response for getDefaultMatrix: {device_sn}")
            return self._cached_responses.get(cache_key, {})

        # Make the API call
        try:
            # Copy the default headers to include them in the request
            headers = self.session.headers.copy()
            headers.update({
                "accept-encoding": "gzip",
            })

            response = await self.session.get(
                path="/device/device/getDefaultMatrix",
                params={"deviceSn": device_sn},
                headers=headers
            )

            # Cache the response
            self._last_api_call_times[cache_key] = now
            self._cached_responses[cache_key] = response
            
            # Update persistent cache
            if self.cache:
                self.cache.update_attribute(device_sn, "defaultMatrix", response)
                
            return response
            
        except (PetLibroConnectionError, PetLibroAPIError) as e:
            _LOGGER.warning(f"Error fetching default matrix for device {device_sn}: {e}")
            if self.cache:
                value, is_fresh = self.cache.get_attribute(device_sn, "defaultMatrix")
                if value:
                    return value
            raise PetLibroAPIError(f"Failed to fetch default matrix: {e}")

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
        return await self.session.request_with_retry("POST", "/device/device/list", json={})

    async def device_base_info(self, serial: str) -> Dict[str, Any]:
        """Get device base info with retry."""
        return await self.session.post_serial("/device/device/baseInfo", serial)

    async def device_real_info(self, serial: str) -> Dict[str, Any]:
        """Get device real info with retry."""
        return await self.session.post_serial("/device/device/realInfo", serial)

    async def device_attribute_settings(self, serial: str) -> Dict[str, Any]:
        """Get device attribute settings with retry."""
        return await self.session.post_serial("/device/setting/getAttributeSetting", serial)

    async def device_grain_status(self, serial: str) -> Dict[str, Any]:
        """Get device grain status with retry."""
        return await self.session.post_serial("/device/data/grainStatus", serial)

    async def device_feeding_plan_today_new(self, serial: str) -> Dict[str, Any]:
        """Get device feeding plan for today with retry."""
        return await self.session.post_serial("/device/feedingPlan/todayNew", serial)

    async def device_wet_feeding_plan(self, serial: str) -> Dict[str, Any]:
        """Get device wet feeding plan with retry."""
        return await self.session.post_serial("/device/wetFeedingPlan/wetListV3", serial)

    # Support for new switch functions
    async def set_feeding_plan(self, serial: str, enable: bool):
        """Set the feeding plan on/off."""
        await self.session.request_with_retry("POST", "/device/setting/updateFeedingPlanSwitch", json={
            "deviceSn": serial,
            "enable": enable
        })

    async def set_child_lock(self, serial: str, enable: bool):
        """Enable or disable the child lock functionality."""
        try:
            response = await self.session.request_with_retry(
                "POST",
                "/device/setting/updateChildLockSwitch", 
                json={"deviceSn": serial, "enable": enable}
            )

            _LOGGER.debug(f"Child lock response: {response}")
            return response
        except Exception as err:
            _LOGGER.error(f"Failed to set child lock for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting child lock: {err}")

    async def set_light_enable(self, serial: str, enable: bool):
        """Enable or disable the light functionality with error handling."""
        try:
            response = await self.session.request_with_retry(
                "POST",
                "/device/setting/updateLightEnableSwitch",
                json={"deviceSn": serial, "enable": enable}
            )
            return response
        except Exception as err:
            _LOGGER.error(f"Failed to set light enable for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting light enable: {err}")

    async def set_light_switch(self, serial: str, enable: bool):
        """Turn the light on or off."""
        await self.session.request_with_retry(
            "POST", 
            "/device/setting/updateLightSwitch", 
            json={
                "deviceSn": serial,
                "enable": enable
            }
        )

    async def set_sound_enable(self, serial: str, enable: bool):
        """Enable or disable the sound functionality."""
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/setting/updateSoundEnableSwitch", 
                json={"deviceSn": serial, "enable": enable}
            )
            return response
        except Exception as err:
            _LOGGER.error(f"Failed to set sound enable for device {serial}: {err}")
            raise PetLibroAPIError(f"Error setting sound enable: {err}")

    async def set_desiccant_frequency(self, serial: str, value: float) -> JSON:
        """Set the desiccant frequency."""
        _LOGGER.debug(f"Setting desiccant frequency: serial={serial}, value={value}")
        try:
            # Generate a dynamic request ID for the manual feeding
            request_id = str(uuid.uuid4()).replace("-", "")

            response = await self.session.request_with_retry(
                "POST", 
                "/device/device/maintenanceFrequencySetting", 
                json={
                    "deviceSn": serial,
                    "key": "DESICCANT",  # Try and find a way to make this dynamic as different devices may have a different key. if too difficult we could just duplicate this block for each key type.
                    "frequency": value,
                    "requestId": request_id,
                    "timeout": 5000
                }
            )
            _LOGGER.debug(f"Desiccant frequency set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set desiccant frequency for device {serial}: {e}")
            raise

    async def set_sound_switch(self, serial: str, enable: bool):
        """Turn the sound on or off."""
        await self.session.request_with_retry(
            "POST", 
            "/device/setting/updateSoundSwitch", 
            json={
                "deviceSn": serial,
                "enable": enable
            }
        )

    async def set_sound_level(self, serial: str, value: float):
        """Set the sound level."""
        _LOGGER.debug(f"Setting sound level: serial={serial}, value={value}")
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/setting/updateVolumeSetting", 
                json={
                    "deviceSn": serial,
                    "volume": value
                }
            )
            _LOGGER.debug(f"Sound level set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set sound level for device {serial}: {e}")
            raise

    async def set_lid_close_time(self, serial: str, value: float):
        """Set the lid close time."""
        _LOGGER.debug(f"Setting lid close time: serial={serial}, value={value}")
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/setting/updateCoverSetting", 
                json={
                    "deviceSn": serial,
                    "coverOpenMode": None,
                    "coverCloseSpeed": None,
                    "closeDoorTimeSec": value
                }
            )
            _LOGGER.debug(f"Lid close time set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set lid close time for device {serial}: {e}")
            raise

    async def set_lid_speed(self, serial: str, value: str):
        """Set the lid speed."""
        _LOGGER.debug(f"Setting lid speed: serial={serial}, value={value}")
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/setting/updateCoverSetting", 
                json={
                    "deviceSn": serial,
                    "coverOpenMode": None,
                    "coverCloseSpeed": value,
                    "closeDoorTimeSec": None
                }
            )
            _LOGGER.debug(f"Lid speed set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set lid speed for device {serial}: {e}")
            raise

    async def set_lid_mode(self, serial: str, value: str):
        """Set the lid mode."""
        _LOGGER.debug(f"Setting lid mode: serial={serial}, value={value}")
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/setting/updateCoverSetting", 
                json={
                    "deviceSn": serial,
                    "coverOpenMode": value,
                    "coverCloseSpeed": None,
                    "closeDoorTimeSec": None
                }
            )
            _LOGGER.debug(f"Lid mode set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set lid mode for device {serial}: {e}")
            raise

    async def set_display_icon(self, serial: str, value: float):
        """Set the display icon."""
        _LOGGER.debug(f"Setting display icon: serial={serial}, value={value}")
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/device/displayMatrix", 
                json={
                    "deviceSn": serial,
                    "screenDisplayId": value,
                    "screenDisplayMatrix": None,
                    "screenLetter": None
                }
            )
            _LOGGER.debug(f"Display icon set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set display icon for device {serial}: {e}")
            raise

    async def set_display_text(self, serial: str, value: str):
        """Set the display text."""
        _LOGGER.debug(f"Setting display text: serial={serial}, value={value}")
        try:
            response = await self.session.request_with_retry(
                "POST", 
                "/device/device/displayMatrix", 
                json={
                    "deviceSn": serial,
                    "screenDisplayId": None,
                    "screenDisplayMatrix": None,
                    "screenLetter": value
                }
            )
            _LOGGER.debug(f"Display text set successfully: {response}")
            return response
        except Exception as e:
            _LOGGER.error(f"Failed to set display text for device {serial}: {e}")
            raise

    async def set_manual_feed(self, serial: str, feed_value=1) -> JSON:
        """Trigger manual feeding for a specific device."""
        _LOGGER.debug(f"Triggering manual feeding for device with serial: {serial}")
        try:
            # Generate a dynamic request ID for the manual feeding
            request_id = str(uuid.uuid4()).replace("-", "")

            # Send the POST request to trigger manual feeding
            response = await self.session.request_with_retry(
                "POST", 
                "/device/device/manualFeeding", 
                json={
                    "deviceSn": serial,
                    "grainNum": int(feed_value),  # Number of grains dispensed, make sure it's an integer and not a float
                    "requestId": request_id  # Use dynamic request ID
                }
            )

            # Handle different response types
            if isinstance(response, int):
                _LOGGER.debug(f"Manual feeding successful, returned code: {response}")
                return response
            return response

        except Exception as err:
            _LOGGER.error(f"Failed to trigger manual feeding for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering manual feeding: {err}")

    async def set_manual_feed_now(self, serial: str):
        """Trigger manual feed now for a specific device. This opens the food bowl door."""
        _LOGGER.debug(f"Triggering manual feed now for device with serial: {serial}")
        
        try:
            # Send the POST request to trigger manual feeding
            await self.session.request_with_retry(
                "POST", 
                "/device/wetFeedingPlan/manualFeedNow", 
                json={
                    "deviceSn": serial,
                    # The plate ID doesn't matter here - the device will always feed from the current bowl regardless of what the plate ID is.
                    # The app also always uses 1 for the plate ID.
                    "plate": 1 
                }
            )

        except Exception as err:
            _LOGGER.error(f"Failed to trigger manual feed now for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering manual feed now: {err}")
        
    async def set_stop_feed_now(self, serial: str, manual_feed_id: int):
        """Trigger stop feed now for a specific device. This closes the food bowl door."""
        _LOGGER.debug(f"Triggering stop feed now for device with serial: {serial}")
        
        try:
            # Send the POST request to trigger stop feeding
            await self.session.request_with_retry(
                "POST", 
                "/device/wetFeedingPlan/stopFeedNow", 
                json={
                    "deviceSn": serial,
                    "feedId": manual_feed_id
                }
            )

        except Exception as err:
            _LOGGER.error(f"Failed to trigger stop feed now for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering stop feed now: {err}")
        
    async def set_rotate_food_bowl(self, serial: str) -> int:
        """Trigger rotate food bowl for a specific device. This rotates the bowls counter-clockwise by one bowl."""
        _LOGGER.debug(f"Triggering rotate food bowl for device with serial: {serial}")
        
        try:
            # Send the POST request to trigger plate position change
            response = await self.session.request_with_retry(
                "POST", 
                "/device/wetFeedingPlan/platePositionChange", 
                json={
                    "deviceSn": serial,
                    # The plate ID doesn't matter here - the device will always rotate one bowl counter-clockwise regardless of what the plate ID is.
                    "plate": 1
                }
            )

            _LOGGER.debug(f"Rotate food bowl successful, new plate position: {response}")
            return response

        except Exception as err:
            _LOGGER.error(f"Failed to trigger rotate food bowl for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering rotate food bowl: {err}")
        
    async def set_feed_audio(self, serial: str):
        """Trigger feed audio for a specific device."""
        _LOGGER.debug(f"Triggering feed audio for device with serial: {serial}")
        
        try:
            # Send the POST request to trigger feed audio
            await self.session.request_with_retry(
                "POST", 
                "/device/wetFeedingPlan/feedAudio", 
                json={
                    "deviceSn": serial
                }
            )

        except Exception as err:
            _LOGGER.error(f"Failed to trigger feed audio for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering feed audio: {err}")

    async def set_desiccant_reset(self, serial: str) -> JSON:
        """Trigger desiccant reset for a specific device."""
        _LOGGER.debug(f"Triggering desiccant reset for device with serial: {serial}")
        
        try:
            # Generate a dynamic request ID
            request_id = str(uuid.uuid4()).replace("-", "")

            # Send the POST request to trigger desiccant reset
            response = await self.session.request_with_retry(
                "POST", 
                "/device/device/desiccantReset", 
                json={
                    "deviceSn": serial,
                    "requestId": request_id,
                    "timeout": 5000
                }
            )

            # Handle different response types
            if isinstance(response, int):
                _LOGGER.debug(f"Desiccant reset set successfully, returned code: {response}")
                return response
            return response

        except Exception as err:
            _LOGGER.error(f"Failed to trigger desiccant reset for device {serial}: {err}")
            raise PetLibroAPIError(f"Error triggering desiccant reset: {err}")

    async def set_manual_lid_open(self, serial: str):
        """Trigger manual lid opening for a specific device."""
        await self.session.request_with_retry(
            "POST", 
            "/device/device/doorStateChange", 
            json={
                "deviceSn": serial,
                "barnDoorState": True,
                "timeout": 8000
            }
        )
    
    async def set_display_on(self, serial: str):
        """Trigger turn display on"""
        await self.session.request_with_retry(
            "POST", 
            "/device/setting/updateDisplayMatrixSetting", 
            json={
                "deviceSn": serial,
                "screenDisplayAgingType": 1,
                "screenDisplayStartTime": None,
                "screenDisplayEndTime": None,
                "screenDisplaySwitch": True
            }
        )
    
    async def set_display_off(self, serial: str):
        """Trigger turn display off"""
        await self.session.request_with_retry(
            "POST", 
            "/device/setting/updateDisplayMatrixSetting", 
            json={
                "deviceSn": serial,
                "screenDisplayAgingType": 1,
                "screenDisplayStartTime": None,
                "screenDisplayEndTime": None,
                "screenDisplaySwitch": False
            }
        )

    async def set_sound_on(self, serial: str):
        """Trigger turn sound on"""
        await self.session.request_with_retry(
            "POST", 
            "/device/setting/updateSoundSetting", 
            json={
                "deviceSn": serial,
                "soundSwitch": True,
                "soundAgingType": 1,
                "soundStartTime": None,
                "soundEndTime": None
            }
        )
    
    async def set_sound_off(self, serial: str):
        """Trigger turn sound off"""
        await self.session.request_with_retry(
            "POST", 
            "/device/setting/updateSoundSetting", 
            json={
                "deviceSn": serial,
                "soundSwitch": False,
                "soundAgingType": 1,
                "soundStartTime": None,
                "soundEndTime": None
            }
        )

## Added this to fix dupe logs
class PetLibroDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        self.api = api
        super().__init__(hass, _LOGGER, name="PetLibroData", update_interval=timedelta(minutes=1))

    async def _async_update_data(self):
        # Fetch data from the API once per update cycle
        return await self.api.fetch_device_data()
