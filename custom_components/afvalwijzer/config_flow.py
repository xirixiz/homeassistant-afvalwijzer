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
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    DOMAIN,
    SENSOR_COLLECTORS_AFVALALERT,
    SENSOR_COLLECTORS_AMSTERDAM,
    SENSOR_COLLECTORS_BURGERPORTAAL,
    SENSOR_COLLECTORS_CIRCULUS,
    SENSOR_COLLECTORS_DEAFVALAPP,
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

_POSTAL_RE = re.compile(r"^\d{4}\s?[A-Za-z]{2}$")

_ALL_LANGUAGES: tuple[str, ...] = ("nl", "en")


def _build_all_collectors() -> list[str]:
    """Return a sorted list of all supported collectors."""
    return sorted(
        {
            *SENSOR_COLLECTORS_MIJNAFVALWIJZER,
            *SENSOR_COLLECTORS_AFVALALERT.keys(),
            *SENSOR_COLLECTORS_AMSTERDAM.keys(),
            *SENSOR_COLLECTORS_BURGERPORTAAL.keys(),
            *SENSOR_COLLECTORS_CIRCULUS.keys(),
            *SENSOR_COLLECTORS_DEAFVALAPP.keys(),
            *SENSOR_COLLECTORS_IRADO.keys(),
            *SENSOR_COLLECTORS_KLIKOGROEP.keys(),
            *SENSOR_COLLECTORS_MONTFERLAND.keys(),
            *SENSOR_COLLECTORS_OMRIN.keys(),
            *SENSOR_COLLECTORS_OPZET.keys(),
            *SENSOR_COLLECTORS_RECYCLEAPP.keys(),
            *SENSOR_COLLECTORS_RD4.keys(),
            *SENSOR_COLLECTORS_REINIS.keys(),
            *SENSOR_COLLECTORS_ROVA.keys(),
            *SENSOR_COLLECTORS_STRAATBEELD.keys(),
            *SENSOR_COLLECTORS_XIMMIO_IDS.keys(),
            "rwm",
        }
    )


ALL_COLLECTORS = _build_all_collectors()

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLLECTOR): vol.In(ALL_COLLECTORS),
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_STREET_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
        vol.Optional(CONF_DATE_ISOFORMAT, default=False): cv.boolean,
        vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
        vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SHOW_FULL_TIMESTAMP, default=DEFAULT_SHOW_FULL_TIMESTAMP): cv.boolean,
        vol.Optional(CONF_INCLUDE_TODAY, default=DEFAULT_INCLUDE_TODAY): cv.boolean,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(_ALL_LANGUAGES),
    }
)


class AfvalwijzerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Afvalwijzer config flow."""

    VERSION = 1

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
            cleaned = _clean_user_input(user_input)

            postal_code = str(cleaned[CONF_POSTAL_CODE])
            street_number = str(cleaned[CONF_STREET_NUMBER])

            if not _validate_postal_code(postal_code):
                errors["base"] = "invalid_postal_code"
            elif not _validate_street_number(street_number):
                errors["base"] = "invalid_street_number"
            else:
                await self.async_set_unique_id(_unique_id_from(cleaned))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Afvalwijzer", data=cleaned)

            user_input = cleaned

        schema = self.add_suggested_values_to_schema(BASE_SCHEMA, user_input or {})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class AfvalwijzerOptionsFlow(config_entries.OptionsFlow):
    """Handle Afvalwijzer options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = dict(self.config_entry.options)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SHOW_FULL_TIMESTAMP,
                    default=current.get(
                        CONF_SHOW_FULL_TIMESTAMP,
                        DEFAULT_SHOW_FULL_TIMESTAMP,
                    ),
                ): cv.boolean,
                vol.Optional(
                    CONF_INCLUDE_TODAY,
                    default=current.get(
                        CONF_INCLUDE_TODAY,
                        DEFAULT_INCLUDE_TODAY,
                    ),
                ): cv.boolean,
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

    exclude_list_raw = str(cleaned.get(CONF_EXCLUDE_LIST, ""))
    cleaned[CONF_EXCLUDE_LIST] = exclude_list_raw.lower()

    suffix_raw = str(cleaned.get(CONF_SUFFIX, ""))
    cleaned[CONF_SUFFIX] = suffix_raw.strip().upper()

    return cleaned


def _unique_id_from(cleaned: dict[str, Any]) -> str:
    """Return a unique ID based on collector and address."""
    collector = str(cleaned.get(CONF_COLLECTOR, "")).strip()
    postal_code = str(cleaned.get(CONF_POSTAL_CODE, "")).strip()
    street_number = str(cleaned.get(CONF_STREET_NUMBER, "")).strip()
    suffix = str(cleaned.get(CONF_SUFFIX, "")).strip()
    return f"{collector}:{postal_code}:{street_number}:{suffix}".strip(":")


def _validate_postal_code(postal_code: str) -> bool:
    """Validate Dutch postal code format (e.g., 1234AB)."""
    return bool(_POSTAL_RE.match(postal_code.strip()))


def _validate_street_number(street_number: str) -> bool:
    """Validate that the street number is a positive integer."""
    return street_number.strip().isdigit()
