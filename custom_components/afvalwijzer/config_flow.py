"""Config flow to configure the AfvalWijzer integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ID
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const.const import (
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_ID,
    CONF_INCLUDE_DATE_TODAY,
    CONF_POSTAL_CODE,
    CONF_PROVIDER,
    CONF_STREET_NUMBER,
    CONF_SUFFIX,
    DOMAIN,
)
from .provider.afvalwijzer import AfvalWijzer


class AfvalWijzerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle AfvalWijzer config flow."""

    VERSION = 1

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> FlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER): str,
                    vol.Required(CONF_POSTAL_CODE): str,
                    vol.Required(CONF_STREET_NUMBER): str,
                    vol.Optional(CONF_SUFFIX): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        session = async_get_clientsession(self.hass)

        afvalwijzer = AfvalWijzer(
            provider=user_input[CONF_PROVIDER],
            postal_code=user_input[CONF_POSTAL_CODE],
            street_number=user_input[CONF_STREET_NUMBER],
            suffix=user_input.get(CONF_SUFFIX),
            include_date_today=CONF_INCLUDE_DATE_TODAY,
            default_label=CONF_DEFAULT_LABEL,
            exclude_list=CONF_EXCLUDE_LIST,
            session=session,
        )

        try:
            await afvalwijzer.waste_data_without_today()
        except Exception as err:
            return await self._show_setup_form(err)

        return self.async_create_entry(
            title=str(CONF_ID),
            data={
                CONF_PROVIDER: user_input[CONF_PROVIDER],
                CONF_POSTAL_CODE: user_input[CONF_POSTAL_CODE],
                CONF_STREET_NUMBER: user_input[CONF_STREET_NUMBER],
                CONF_SUFFIX: user_input.get(CONF_SUFFIX),
            },
        )
