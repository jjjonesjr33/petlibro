"""Config flow for Petlibro integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_TOKEN, CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .api import PetLibroAPI
from .const import (
    DEFAULT_FEED,
    DEFAULT_WATER,
    DEFAULT_WEIGHT,
    DOMAIN,
    CommonAPIKeys as API,
    Gender,
    UnitTypes,
)
from .exceptions import PetLibroCannotConnect, PetLibroInvalidAuth
from .hub import PetLibroHub
from .member import Member

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): vol.In(["US"]),
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class PetlibroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Petlibro."""

    VERSION = 1

    token: str
    email: str
    region: str
    password: str  # Store the password temporarily for API login

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Prevent duplicate entries for the same email
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})

            # Store user input values
            self.email = user_input[CONF_EMAIL]
            self.password = user_input[CONF_PASSWORD]
            self.region = user_input[CONF_REGION]

            # Validate input and login to the API
            if not (error := await self._validate_input()):
                # If validation passes, create the entry with email, password, and token
                return self.async_create_entry(
                    title=self.email,
                    data={
                        CONF_REGION: self.region,
                        CONF_EMAIL: self.email,
                        CONF_PASSWORD: self.password,  # Save password in entry
                        CONF_API_TOKEN: self.token
                    }
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle a reauthorization flow request."""
        self.email = entry_data[CONF_EMAIL]
        self.region = entry_data[CONF_REGION]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, str] | None = None) -> ConfigFlowResult:
        """Handle user's reauth credentials."""
        errors = {}

        if user_input:
            entry_id = self.context["entry_id"]
            if entry := self.hass.config_entries.async_get_entry(entry_id):
                user_input = user_input | {CONF_EMAIL: self.email, CONF_REGION: self.region}
                self.password = user_input[CONF_PASSWORD]

                # Validate input and login to the API again
                if not (error := await self._validate_input()):
                    # Update the config entry with the new token and password after re-auth
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_EMAIL: self.email,
                            CONF_REGION: self.region,
                            CONF_PASSWORD: self.password,  # Ensure password is updated
                            CONF_API_TOKEN: self.token
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_EMAIL: self.email, CONF_REGION: self.region},
            errors=errors,
        )

    async def _validate_input(self) -> str:
        """Validate the user input allows us to connect.

        Validate email, password, and region, then attempt API login.
        """
        try:
            api = PetLibroAPI(
                async_get_clientsession(self.hass),
                self.hass.config.time_zone,
                self.region,
                self.email,
                self.password
            )

            self.token = await api.login(self.email, self.password)
            _LOGGER.debug(f"Login successful, token: {self.token}")
        except PetLibroCannotConnect:
            return "cannot_connect"
        except PetLibroInvalidAuth:
            return "invalid_auth"
        except Exception as e:
            _LOGGER.exception("Unexpected exception during validation: %s", e)
            return "unknown"

        return ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> PetlibroOptionsFlow:
        """Get the options flow for this handler."""
        return PetlibroOptionsFlow()


class PetlibroOptionsFlow(OptionsFlow):
    """Handle an options flow for Petlibro."""

    _SENTINEL = object()

    def __init__(self):
        """Initialise Petlibro Options Flow."""
        self._data: dict[str, Any] = {}  # For storing temporary data.
        self.entry: ConfigEntry | None = None
        self.hub: PetLibroHub | None = None
        self.api: PetLibroAPI | None = None
        self.member: Member | None = None

    # ------------------------------
    # Options Flow Steps
    # ------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial options menu."""

        _LOGGER.debug("Starting Petlibro options flow.")
        self.entry = self.config_entry
        self.hub = self.hass.data[DOMAIN][self.handler]
        self.api = self.hub.api
        self.member = self.hub.member
        self._data.clear()

        _LOGGER.debug(
            "Started Petlibro options flow for account %s", self.entry.data[CONF_EMAIL]
        )

        # Using a menu so more things can be added later.
        return self.async_show_menu(menu_options=["account_settings"])

    async def async_step_account_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle account settings."""

        if not self.member:
            return self.async_abort(reason="account_update_nomember")

        user_input = user_input or {}
        if user_input:
            update_setting = self.collect_updates(
                fields=(API.FEED_UNIT, API.WATER_UNIT, API.WEIGHT_UNIT),
                user_input=user_input.pop("measurement_unit", {}),
                enum_cls=UnitTypes,
            )

            update_info = self.collect_updates(
                fields=(API.NICKNAME, API.GENDER),
                user_input=user_input,
                special={
                    API.NICKNAME: lambda v: v or "",
                    API.GENDER: lambda v: self.validate_enum(API.GENDER, v, Gender),
                },
            )

            if not (update_info or update_setting):
                _LOGGER.debug("No account settings were changed.")
                return self.async_abort(reason="account_update_nochanges")

            no_error = await self.api.member_update_info(update_info, update_setting)
            await self.hub.async_refresh(force_member=True)

            return self.async_abort(
                reason="account_update_success" if no_error else "error_check_logs"
            )

        _LOGGER.debug("Showing account settings form.")
        return self._show_account_settings_form(user_input)

    # ------------------------------
    # Form Builders
    # ------------------------------

    def _show_account_settings_form(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Build and show the account settings form."""

        return self.async_show_form(
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        str(API.NICKNAME),
                        description={
                            "suggested_value": user_input.get(
                                API.NICKNAME, getattr(self.member, API.NICKNAME, "")
                            )
                        },
                    ): str,
                    vol.Required(
                        str(API.GENDER),
                        default=user_input.get(
                            API.GENDER, getattr(self.member, API.GENDER, str(Gender.NONE))
                        ),
                    ): selector(
                        {
                            "select": {
                                "options": [g.name.lower() for g in Gender],
                                "mode": "dropdown",
                                "translation_key": "member_gender",
                            }
                        }
                    ),
                    vol.Required("measurement_unit"): section(
                        self._get_measurement_schema(user_input), {"collapsed": True}
                    ),
                }
            ),
            description_placeholders={
                "email": getattr(self.member, API.EMAIL, "").replace(".", "&#46;")
            },  # Replace full-stops with "&#46;" in the email string to prevent hyperlinking.
        )

    def _get_measurement_schema(self, user_input: dict[str, Any]) -> vol.Schema:
        """Build and return the measurement units schema."""
        return vol.Schema(
            {
                vol.Required(
                    str(API.FEED_UNIT),
                    default=user_input.get(
                        API.FEED_UNIT, getattr(self.member, API.FEED_UNIT, DEFAULT_FEED.name)
                    ),
                ): self._unit_selector(
                    (UnitTypes.CUPS, UnitTypes.OUNCES, UnitTypes.GRAMS, UnitTypes.MILLILITERS)
                ),
                vol.Required(
                    str(API.WATER_UNIT),
                    default=user_input.get(
                        API.WATER_UNIT, getattr(self.member, API.WATER_UNIT, DEFAULT_WATER.name)
                    ),
                ): self._unit_selector((UnitTypes.OUNCES, UnitTypes.MILLILITERS)),
                vol.Required(
                    str(API.WEIGHT_UNIT),
                    default=user_input.get(
                        API.WEIGHT_UNIT,
                        getattr(self.member, API.WEIGHT_UNIT, DEFAULT_WEIGHT.name),
                    ),
                ): self._unit_selector((UnitTypes.POUNDS, UnitTypes.KILOGRAMS)),
            }
        )

    def _unit_selector(self, options: tuple[Enum, ...]) -> Any:
        """Return a dropdown selector for measurement unit options."""
        return selector(
            {
                "select": {
                    "options": [o.name.lower() for o in options],
                    "mode": "dropdown",
                    "translation_key": "unit_type",
                }
            }
        )

    # ------------------------------
    # Validation & Updates
    # ------------------------------

    def validate_enum(self, api_key: str, form_value: Any, enum_cls: type[Enum]) -> Any:
        """Check if the provided form value is a valid Enum member."""
        if isinstance(form_value, enum_cls):
            return form_value.value

        form_value_str = str(form_value).upper()
        if form_value_str in enum_cls.__members__:
            return enum_cls[form_value_str].value

        _LOGGER.error("Invalid value: %s for API key: %s", form_value, api_key)
        return None

    def collect_updates(
        self,
        fields: tuple[str, ...],
        user_input: dict[str, Any],
        enum_cls: type[Enum] | None = None,
        special: dict[str, Callable[[Any], Any]] | None = None,
    ) -> dict[str, Any]:
        """Check and collect which settings have been updated."""
        updates: dict[str, Any] = {}

        for api_key in fields:
            form_value = user_input.get(api_key)
            current_value = getattr(self.member, api_key, self._SENTINEL)

            if current_value is self._SENTINEL:
                _LOGGER.error("Unsupported API key: %s", api_key)
                continue
            if form_value == current_value:
                continue

            if special and api_key in special:
                api_value = special[api_key](form_value)
            elif enum_cls:
                api_value = self.validate_enum(api_key, form_value, enum_cls)
                if api_value is None:
                    continue
            else:
                api_value = form_value

            updates[api_key] = api_value

        return updates
