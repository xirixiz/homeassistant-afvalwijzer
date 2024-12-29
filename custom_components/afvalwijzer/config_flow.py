import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
import logging

from .const.const import (
    DOMAIN,
    CONF_COLLECTOR,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
)

# Extract keys from the dictionaries
collectors_opzet = SENSOR_COLLECTORS_OPZET.keys()
collectors_icalendar = SENSOR_COLLECTORS_ICALENDAR.keys()
collectors_klikogroep = SENSOR_COLLECTORS_KLIKOGROEP.keys()
collectors_afvalwijzer = SENSOR_COLLECTORS_AFVALWIJZER
collectors_ximmio = SENSOR_COLLECTORS_XIMMIO.keys()
collectors_ximmio_ids = SENSOR_COLLECTORS_XIMMIO_IDS.keys()
collectors_rd4 = SENSOR_COLLECTORS_RD4.keys()
collectors_afvalalert = SENSOR_COLLECTORS_AFVALALERT.keys()
collectors_circulus = SENSOR_COLLECTORS_CIRCULUS.keys()
collectors_rova = SENSOR_COLLECTORS_ROVA.keys()
collectors_burgerportaal = SENSOR_COLLECTORS_BURGERPORTAAL.keys()
collectors_deafvalapp = SENSOR_COLLECTORS_DEAFVALAPP.keys()
# collectors_rwm = SENSOR_COLLECTORS_RWM.keys() # No key set for this provider

# Combine all collectors into a single list
all_collectors = (
    list(collectors_opzet) +
    list(collectors_icalendar) +
    list(collectors_klikogroep) +
    list(collectors_afvalwijzer) +
    list(collectors_ximmio) +
    list(collectors_ximmio_ids) +
    list(collectors_rd4) +
    list(collectors_afvalalert) +
    list(collectors_circulus) +
    list(collectors_rova) +
    list(collectors_burgerportaal) +
    list(collectors_deafvalapp) +
    ["rwm"]  # Add 'rwm' as a string directly
)

# Sort all collectors
unique_collectors = sorted(set(all_collectors))

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_COLLECTOR): vol.In(unique_collectors),  # Dropdown list for CONF_COLLECTOR
    vol.Required(CONF_POSTAL_CODE): cv.string,
    vol.Required(CONF_STREET_NUMBER): cv.string,
    vol.Optional(CONF_SUFFIX, default=""): cv.string,
    vol.Optional(CONF_USERNAME, default=""): cv.string,
    vol.Optional(CONF_PASSWORD, default=""): cv.string,
    vol.Optional(CONF_EXCLUDE_PICKUP_TODAY, default=True): cv.boolean,
    vol.Optional(CONF_DATE_ISOFORMAT, default=False): cv.boolean,
    vol.Optional(CONF_DEFAULT_LABEL, default="geen"): cv.string,
    vol.Optional(CONF_EXCLUDE_LIST, default=""): cv.string,
})

_LOGGER = logging.getLogger(__name__)

class AfvalwijzerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Afvalwijzer."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Ensure CONF_* is saved lowercase
            user_input[CONF_COLLECTOR] = user_input.get(CONF_COLLECTOR, "").lower()
            user_input[CONF_EXCLUDE_LIST] = user_input.get(CONF_EXCLUDE_LIST, "").lower()

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
            description_placeholders={},
        )

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
