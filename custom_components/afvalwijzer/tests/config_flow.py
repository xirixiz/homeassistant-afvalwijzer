import aiohttp
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.helpers import config_validation as cv

DOMAIN = "trash_collection"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("provider", default="mijnafvalwijzer"): cv.string,
                vol.Required("postal_code"): cv.string,
                vol.Required("street_number"): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    return True


class TrashCollectionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Perform validation or configuration steps here
            if not await validate_user_input(self.hass, user_input):
                errors["base"] = "Invalid input, please check your information."

            if not errors:
                return self.async_create_entry(
                    title="Trash Collection", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA[DOMAIN],
            errors=errors,
        )


async def validate_user_input(hass, user_input):
    provider = user_input["provider"]
    postal_code = user_input["postal_code"]
    street_number = user_input["street_number"]

    url = f"https://json.mijnafvalwijzer.nl/?method=postcodecheck&postcode={postal_code}&street=&huisnummer={street_number}&toevoeging=&apikey=<YOUR_API_KEY>"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

    # Replace the following condition with your own validation logic
    return data.get("data", {}).get("ophaaldagen", {}).get(provider) is not None
