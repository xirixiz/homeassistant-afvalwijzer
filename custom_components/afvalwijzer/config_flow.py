import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const.const import (
    DOMAIN,
    CONF_COLLECTOR,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_COLLECTOR): cv.string,
    vol.Required(CONF_POSTAL_CODE): cv.string,
    vol.Required(CONF_STREET_NUMBER): cv.string,
    vol.Optional(CONF_SUFFIX, default=""): cv.string,
    vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
    vol.Optional(CONF_DATE_ISOFORMAT, default=False): cv.boolean,
    vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
    vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
})


class AfvalwijzerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Afvalwijzer."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Perform validation
            if not self._validate_postal_code(user_input.get(CONF_POSTAL_CODE)):
                errors["postal_code"] = "config.error.invalid_postal_code"
            elif not self._validate_street_number(user_input.get(CONF_STREET_NUMBER)):
                errors["street_number"] = "config.error.invalid_street_number"
            else:
                # Validation passed, create the entry
                return self.async_create_entry(title="Afvalwijzer", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "provider": "e.g., mijnafvalwijzer",
                "postal_code": "e.g., 1234AB",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AfvalwijzerOptionsFlow()

    def _validate_postal_code(self, postal_code):
        """Validate the postal code format."""
        return (
            isinstance(postal_code, str)
            and len(postal_code) == 6
            and postal_code[:4].isdigit()
            and postal_code[4:].isalpha()
        )

    def _validate_street_number(self, street_number):
        """Validate the street number."""
        return street_number.isdigit()


class AfvalwijzerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Afvalwijzer."""

    def __init__(self):
        """Initialize the options flow."""

    async def async_step_init(self, user_input=None):
        """Handle options configuration."""
        # Haal bestaande opties op uit config_entry.options
        current_options = self.options or {}

        if user_input is not None:
            # Sla wijzigingen op en creëer een nieuwe entry
            return self.async_create_entry(title="", data=user_input)

        # Toon formulier met bestaande waarden als defaults
        options_schema = vol.Schema({
            vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=current_options.get(CONF_EXCLUDE_PICKUP_TODAY, True)): cv.boolean,
            vol.Optional(CONF_DATE_ISOFORMAT, default=current_options.get(CONF_DATE_ISOFORMAT, False)): cv.boolean,
            vol.Optional(CONF_DEFAULT_LABEL, default=current_options.get(CONF_DEFAULT_LABEL, "geen")): cv.string,
            vol.Optional(CONF_EXCLUDE_LIST, default=current_options.get(CONF_EXCLUDE_LIST, "")): cv.string,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "exclude_pickup_today": "Exclude today's pickup",
                "date_isoformat": "Use ISO date format",
            },
        )


