import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
import logging

from .const.const import (
    DOMAIN,
    _LOGGER,
    CONF_COLLECTOR,
    CONF_POSTAL_CODE,
    CONF_STREET_NUMBER,
    CONF_SECONDARY_COLLECTOR,
    CONF_SUFFIX,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_DATE_ISOFORMAT,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_AFVALALERT,
    SENSOR_COLLECTORS_BURGERPORTAAL,
    SENSOR_COLLECTORS_CIRCULUS,
    SENSOR_COLLECTORS_CLEANPROFS,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_ICALENDAR,
    SENSOR_COLLECTORS_IRADO,
    SENSOR_COLLECTORS_IRADO,
    SENSOR_COLLECTORS_KLIKOGROEP,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_ROVA,
    SENSOR_COLLECTORS_XIMMIO_IDS,
)

# Define all collectors with a tag (True = primary, False = secondary)
all_collectors_tagged = (
    [(collector, True) for collector in SENSOR_COLLECTORS_AFVALWIJZER] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_AFVALALERT.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_BURGERPORTAAL.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_CIRCULUS.keys()] +  # Primary
    [(collector, False) for collector in SENSOR_COLLECTORS_CLEANPROFS.keys()] +  # Secondary
    [(collector, True) for collector in SENSOR_COLLECTORS_DEAFVALAPP.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_ICALENDAR.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_IRADO.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_KLIKOGROEP.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_OPZET.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_RD4.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_ROVA.keys()] +  # Primary
    [(collector, True) for collector in SENSOR_COLLECTORS_XIMMIO_IDS.keys()] +  # Primary
    [("rwm", True)]  # Primary
)

# Extract primary collectors (where tag is True)
all_collectors = sorted({collector for collector, is_primary in all_collectors_tagged if is_primary})
# Extract secondary collectors (where tag is False)
secondary_collectors = sorted({collector for collector, is_primary in all_collectors_tagged if not is_primary})

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_COLLECTOR): vol.In(all_collectors),
    vol.Required(CONF_POSTAL_CODE): cv.string,
    vol.Required(CONF_STREET_NUMBER): cv.string,
    vol.Optional(CONF_SUFFIX, default=""): cv.string,
    vol.Optional(CONF_SECONDARY_COLLECTOR): vol.In(secondary_collectors),
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
            user_input[CONF_SECONDARY_COLLECTOR] = user_input.get(CONF_SECONDARY_COLLECTOR, "").lower()

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
