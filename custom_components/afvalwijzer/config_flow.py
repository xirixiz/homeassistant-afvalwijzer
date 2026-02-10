"""Config flow for Afvalwijzer."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const.const import (
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    DOMAIN,
    SENSOR_COLLECTORS_AMSTERDAM,
    SENSOR_COLLECTORS_BURGERPORTAAL,
    SENSOR_COLLECTORS_CIRCULUS,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_ICALENDAR,
    SENSOR_COLLECTORS_IRADO,
    SENSOR_COLLECTORS_KLIKOGROEP,
    SENSOR_COLLECTORS_MIJNAFVALWIJZER,
    SENSOR_COLLECTORS_MONTFERLAND,
    SENSOR_COLLECTORS_OMRIN,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_RECYCLEAPP,
    SENSOR_COLLECTORS_REINIS,
    SENSOR_COLLECTORS_ROVA,
    SENSOR_COLLECTORS_STRAATBEELD,
    SENSOR_COLLECTORS_XIMMIO_IDS,
)

# Options keys
CONF_SHOW_FULL_TIMESTAMP = "show_full_timestamp"
CONF_LANGUAGE = "language"
CONF_INCLUDE_TODAY = "include_today"

DEFAULT_SHOW_FULL_TIMESTAMP = True
DEFAULT_LANGUAGE = "nl"
DEFAULT_INCLUDE_TODAY = True

DEFAULT_DEFAULT_LABEL = "geen"
DEFAULT_EXCLUDE_LIST = ""
DEFAULT_FRIENDLY_NAME = ""

_POSTAL_CODE_BE_RE = re.compile(r"^\d{4}$")
_POSTAL_CODE_NL_RE = re.compile(r"^\d{4}\s?[A-Za-z]{2}$")
_ALL_LANGUAGES: tuple[str, ...] = ("nl", "en")

_RECONFIGURE_STEP_ID = "reconfigure"

ALL_COLLECTORS = sorted(
    {
        *SENSOR_COLLECTORS_MIJNAFVALWIJZER,
        *SENSOR_COLLECTORS_AMSTERDAM.keys(),
        *SENSOR_COLLECTORS_BURGERPORTAAL.keys(),
        *SENSOR_COLLECTORS_CIRCULUS.keys(),
        *SENSOR_COLLECTORS_DEAFVALAPP.keys(),
        *SENSOR_COLLECTORS_ICALENDAR.keys(),
        *SENSOR_COLLECTORS_IRADO.keys(),
        *SENSOR_COLLECTORS_KLIKOGROEP.keys(),
        *SENSOR_COLLECTORS_MONTFERLAND.keys(),
        *SENSOR_COLLECTORS_OMRIN.keys(),
        *SENSOR_COLLECTORS_OPZET.keys(),
        *SENSOR_COLLECTORS_RD4.keys(),
        *SENSOR_COLLECTORS_RECYCLEAPP.keys(),
        *SENSOR_COLLECTORS_REINIS.keys(),
        *SENSOR_COLLECTORS_ROVA.keys(),
        "rwm",
        *SENSOR_COLLECTORS_STRAATBEELD.keys(),
        *SENSOR_COLLECTORS_XIMMIO_IDS.keys(),
    }
)

COLLECTOR_SCHEMA = vol.Schema({vol.Required(CONF_COLLECTOR): vol.In(ALL_COLLECTORS)})


def _address_schema_for(collector: str | None) -> vol.Schema:
    """Return an address schema depending on the collector."""
    schema_dict: dict[vol.Marker, Any] = {
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
    }

    if collector in SENSOR_COLLECTORS_RECYCLEAPP:
        schema_dict[vol.Required(CONF_STREET_NAME)] = cv.string

    schema_dict[vol.Optional(CONF_FRIENDLY_NAME, default="")] = cv.string

    return vol.Schema(schema_dict)


def _reconfigure_schema_for(current: dict[str, Any]) -> vol.Schema:
    """Return a schema for reconfiguration, pre-filled with current values."""
    collector = current.get(CONF_COLLECTOR, "")

    schema_dict: dict[vol.Marker, Any] = {
        vol.Required(CONF_COLLECTOR, default=current.get(CONF_COLLECTOR, "")): vol.In(
            ALL_COLLECTORS
        ),
        vol.Required(
            CONF_POSTAL_CODE, default=current.get(CONF_POSTAL_CODE, "")
        ): cv.string,
        vol.Required(
            CONF_HOUSE_NUMBER, default=current.get(CONF_HOUSE_NUMBER, "")
        ): cv.string,
        vol.Optional(CONF_SUFFIX, default=current.get(CONF_SUFFIX, "")): cv.string,
    }

    if collector in SENSOR_COLLECTORS_RECYCLEAPP:
        schema_dict[
            vol.Required(CONF_STREET_NAME, default=current.get(CONF_STREET_NAME, ""))
        ] = cv.string

    schema_dict[
        vol.Optional(CONF_FRIENDLY_NAME, default=current.get(CONF_FRIENDLY_NAME, ""))
    ] = cv.string

    return vol.Schema(schema_dict)


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_SHOW_FULL_TIMESTAMP, default=DEFAULT_SHOW_FULL_TIMESTAMP
        ): cv.boolean,
        vol.Optional(CONF_INCLUDE_TODAY, default=DEFAULT_INCLUDE_TODAY): cv.boolean,
        vol.Optional(CONF_DEFAULT_LABEL, default=DEFAULT_DEFAULT_LABEL): cv.string,
        vol.Optional(CONF_EXCLUDE_LIST, default=DEFAULT_EXCLUDE_LIST): cv.string,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(_ALL_LANGUAGES),
    }
)


class AfvalwijzerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Afvalwijzer config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._reconfigure_entry: config_entries.ConfigEntry | None = None
        self._collector: str | None = None

    @staticmethod
    def _validate_postal_code(postal_code: str, collector: str) -> bool:
        """Validate Dutch postal code format (e.g., 1234AB)."""
        return _validate_postal_code(postal_code, collector)

    @staticmethod
    def _validate_house_number(house_number: str) -> bool:
        """Validate that the street number is a positive integer."""
        return _validate_house_number(house_number)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return AfvalwijzerOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._collector = str(user_input[CONF_COLLECTOR])
            return await self.async_step_address()
        return self.async_show_form(
            step_id="user", data_schema=COLLECTOR_SCHEMA, errors=errors
        )

    async def async_step_address(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Handle address details after collector selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            collector = self._collector or str(user_input.get(CONF_COLLECTOR, ""))
            cleaned = _clean_user_input(user_input)
            cleaned[CONF_COLLECTOR] = collector

            postal_code = str(cleaned[CONF_POSTAL_CODE])
            house_number = str(cleaned[CONF_HOUSE_NUMBER])
            collector = str(cleaned[CONF_COLLECTOR])

            if not self._validate_postal_code(postal_code, collector):
                errors["base"] = "invalid_postal_code"
            elif not self._validate_house_number(house_number):
                errors["base"] = "invalid_house_number"
            else:
                await self.async_set_unique_id(_unique_id_from(cleaned))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Afvalwijzer", data=cleaned)

            user_input = cleaned

        schema = self.add_suggested_values_to_schema(
            _address_schema_for(self._collector), user_input or {}
        )
        return self.async_show_form(
            step_id="address", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Handle reconfiguration of an existing config entry."""
        self._reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if self._reconfigure_entry is None:
            return self.async_abort(reason="reconfigure_failed")

        current = dict(self._reconfigure_entry.data)
        current.pop("id", None)
        return await self._async_show_reconfigure_form(user_input, current)

    async def _async_show_reconfigure_form(
        self,
        user_input: dict[str, Any] | None,
        current: dict[str, Any],
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned = _clean_user_input(user_input)

            postal_code = str(cleaned[CONF_POSTAL_CODE])
            house_number = str(cleaned[CONF_HOUSE_NUMBER])
            collector = str(cleaned[CONF_COLLECTOR])

            if not self._validate_postal_code(postal_code, collector):
                errors["base"] = "invalid_postal_code"
            elif not self._validate_house_number(house_number):
                errors["base"] = "invalid_house_number"
            else:
                assert self._reconfigure_entry is not None

                await self.async_set_unique_id(_unique_id_from(cleaned))
                self.hass.config_entries.async_update_entry(
                    self._reconfigure_entry,
                    data=cleaned,
                )
                await self.hass.config_entries.async_reload(
                    self._reconfigure_entry.entry_id
                )
                return self.async_abort(reason="reconfigure_successful")

            user_input = cleaned

        suggested = current.copy()
        if user_input:
            suggested.update(user_input)

        schema = self.add_suggested_values_to_schema(
            _reconfigure_schema_for(suggested), suggested
        )
        return self.async_show_form(
            step_id=_RECONFIGURE_STEP_ID,
            data_schema=schema,
            errors=errors,
        )


class AfvalwijzerOptionsFlow(config_entries.OptionsFlow):
    """Handle Afvalwijzer options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Handle the options step."""
        if user_input is not None:
            cleaned = _clean_options_input(user_input)

            result = self.async_create_entry(title="", data=cleaned)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._config_entry.entry_id)
            )
            return result

        current = dict(self._config_entry.options)
        include_today = bool(current.get(CONF_INCLUDE_TODAY, DEFAULT_INCLUDE_TODAY))

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SHOW_FULL_TIMESTAMP,
                    default=current.get(
                        CONF_SHOW_FULL_TIMESTAMP, DEFAULT_SHOW_FULL_TIMESTAMP
                    ),
                ): cv.boolean,
                vol.Optional(
                    CONF_INCLUDE_TODAY,
                    default=include_today,
                ): cv.boolean,
                vol.Optional(
                    CONF_DEFAULT_LABEL,
                    default=current.get(CONF_DEFAULT_LABEL, DEFAULT_DEFAULT_LABEL),
                ): cv.string,
                vol.Optional(
                    CONF_EXCLUDE_LIST,
                    default=current.get(CONF_EXCLUDE_LIST, DEFAULT_EXCLUDE_LIST),
                ): cv.string,
                vol.Optional(
                    CONF_LANGUAGE,
                    default=current.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                ): vol.In(_ALL_LANGUAGES),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


def _clean_user_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize and sanitize user input."""
    cleaned = dict(user_input)

    postal_code_raw = str(cleaned.get(CONF_POSTAL_CODE, ""))
    cleaned[CONF_POSTAL_CODE] = postal_code_raw.replace(" ", "").upper()

    suffix_raw = str(cleaned.get(CONF_SUFFIX, ""))
    cleaned[CONF_SUFFIX] = suffix_raw.strip().upper()

    street_name_raw = str(cleaned.get(CONF_STREET_NAME, ""))
    cleaned[CONF_STREET_NAME] = street_name_raw.strip()

    return cleaned


def _clean_options_input(options_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize options and keep backward compatible legacy keys."""
    cleaned = dict(options_input)

    exclude_list_raw = str(cleaned.get(CONF_EXCLUDE_LIST, DEFAULT_EXCLUDE_LIST))
    cleaned[CONF_EXCLUDE_LIST] = exclude_list_raw.lower()

    default_label_raw = str(cleaned.get(CONF_DEFAULT_LABEL, DEFAULT_DEFAULT_LABEL))
    cleaned[CONF_DEFAULT_LABEL] = default_label_raw.strip() or DEFAULT_DEFAULT_LABEL

    include_today = bool(cleaned.get(CONF_INCLUDE_TODAY, DEFAULT_INCLUDE_TODAY))

    cleaned[CONF_EXCLUDE_PICKUP_TODAY] = not include_today

    return cleaned


def _unique_id_from(cleaned: dict[str, Any]) -> str:
    """Return a unique ID based on collector and address."""
    collector = str(cleaned.get(CONF_COLLECTOR, "")).strip()
    postal_code = str(cleaned.get(CONF_POSTAL_CODE, "")).strip()
    house_number = str(cleaned.get(CONF_HOUSE_NUMBER, "")).strip()
    suffix = str(cleaned.get(CONF_SUFFIX, "")).strip()
    street_name = str(cleaned.get(CONF_STREET_NAME, "")).strip()

    if street_name:
        return f"{collector}:{postal_code}:{house_number}:{suffix}:{street_name}".strip(
            ":"
        )
    else:
        return f"{collector}:{postal_code}:{house_number}:{suffix}".strip(":")


def _validate_postal_code(postal_code: str, collector: str) -> bool:
    """Validate Dutch postal code format (e.g., 1234AB)."""
    if collector in SENSOR_COLLECTORS_RECYCLEAPP:
        return bool(_POSTAL_CODE_BE_RE.match(postal_code.strip()))
    return bool(_POSTAL_CODE_NL_RE.match(postal_code.strip()))


def _validate_house_number(house_number: str) -> bool:
    """Validate that the street number is a positive integer."""
    return house_number.strip().isdigit()
