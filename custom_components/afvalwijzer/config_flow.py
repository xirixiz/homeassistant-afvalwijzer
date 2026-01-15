"""Afvalwijzer integration."""

import re

import voluptuous as vol

from homeassistant import config_entries
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

DOMAIN = "afvalwijzer"

_POSTAL_RE = re.compile(r"^\d{4}\s?[A-Za-z]{2}$")

all_collectors = sorted(
    set(
        list(SENSOR_COLLECTORS_MIJNAFVALWIJZER)
        + list(SENSOR_COLLECTORS_AFVALALERT.keys())
        + list(SENSOR_COLLECTORS_AMSTERDAM.keys())
        + list(SENSOR_COLLECTORS_BURGERPORTAAL.keys())
        + list(SENSOR_COLLECTORS_CIRCULUS.keys())
        + list(SENSOR_COLLECTORS_DEAFVALAPP.keys())
        + list(SENSOR_COLLECTORS_IRADO.keys())
        + list(SENSOR_COLLECTORS_KLIKOGROEP.keys())
        + list(SENSOR_COLLECTORS_MONTFERLAND.keys())
        + list(SENSOR_COLLECTORS_OMRIN.keys())
        + list(SENSOR_COLLECTORS_OPZET.keys())
        + list(SENSOR_COLLECTORS_RECYCLEAPP.keys())
        + list(SENSOR_COLLECTORS_RD4.keys())
        + list(SENSOR_COLLECTORS_REINIS.keys())
        + list(SENSOR_COLLECTORS_ROVA.keys())
        + list(SENSOR_COLLECTORS_STRAATBEELD.keys())
        + list(SENSOR_COLLECTORS_XIMMIO_IDS.keys())
        + ["rwm"]
    )
)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLLECTOR): vol.In(all_collectors),
        vol.Required(CONF_POSTAL_CODE): cv.string,
        vol.Required(CONF_STREET_NUMBER): cv.string,
        vol.Optional(CONF_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
        vol.Optional(CONF_DATE_ISOFORMAT, default=False): cv.boolean,
        vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
        vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
    }
)


class AfvalwijzerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Afvalwijzer config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            collector = user_input.get(CONF_COLLECTOR, "")
            exclude_list = user_input.get(CONF_EXCLUDE_LIST, "")
            postal_code_raw = user_input.get(CONF_POSTAL_CODE, "")
            street_number_raw = user_input.get(CONF_STREET_NUMBER, "")
            suffix = user_input.get(CONF_SUFFIX, "")

            postal_code = postal_code_raw.replace(" ", "").upper()
            user_input[CONF_POSTAL_CODE] = postal_code
            user_input[CONF_COLLECTOR] = collector
            user_input[CONF_EXCLUDE_LIST] = exclude_list.lower()

            if not self._validate_postal_code(postal_code):
                errors["base"] = "invalid_postal_code"
            elif not self._validate_street_number(street_number_raw):
                errors["base"] = "invalid_street_number"
            else:
                unique = (
                    f"{collector}:{postal_code}:{street_number_raw}:{suffix}".strip(":")
                )
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Afvalwijzer", data=user_input)

        schema = self.add_suggested_values_to_schema(BASE_SCHEMA, user_input or {})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def _validate_postal_code(self, postal_code: str) -> bool:
        return isinstance(postal_code, str) and bool(
            _POSTAL_RE.match(postal_code.strip())
        )

    def _validate_street_number(self, street_number: str) -> bool:
        return isinstance(street_number, str) and street_number.strip().isdigit()
