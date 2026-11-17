"""Flow-level tests for the user, address and import steps of the config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.afvalwijzer.config_flow import (
    _clean_options_input,
    _clean_user_input,
    _unique_id_from,
)
from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_EXCLUDE_LIST,
    CONF_EXCLUDE_PICKUP_TODAY,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_INCLUDE_TODAY,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    DOMAIN,
)
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture(autouse=True)
def _no_real_setup():
    """Keep a created entry from being set up for real; the setup has its own tests."""
    with patch(
        "custom_components.afvalwijzer.async_setup_entry",
        AsyncMock(return_value=True),
    ) as mock:
        yield mock


async def _start(hass, collector):
    """Start the user flow and choose a collector; return the address form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COLLECTOR: collector}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "address"
    return result


def _address(postal_code="1234 ab", house_number="1", suffix="", **extra):
    return {
        CONF_POSTAL_CODE: postal_code,
        CONF_HOUSE_NUMBER: house_number,
        CONF_SUFFIX: suffix,
        **extra,
    }


# --- user and address steps -----------------------------------------------------------


async def test_user_flow_creates_an_entry_with_a_cleaned_address(hass):
    """Collector, then address: the postal code and suffix are normalized."""
    result = await _start(hass, "mijnafvalwijzer")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _address("1234 ab", " 12 ", " a ")
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Afvalwijzer"
    assert result["data"][CONF_COLLECTOR] == "mijnafvalwijzer"
    assert result["data"][CONF_POSTAL_CODE] == "1234AB"
    assert result["data"][CONF_SUFFIX] == "A"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "mijnafvalwijzer:1234AB: 12 :A".replace(" 12 ", "12")


async def test_user_flow_without_a_suffix_has_a_short_unique_id(hass):
    """No suffix: no trailing separator in the unique id."""
    result = await _start(hass, "rova")

    await hass.config_entries.flow.async_configure(result["flow_id"], _address())

    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "rova:1234AB:1"


@pytest.mark.parametrize(
    ("postal_code", "house_number", "error"),
    [
        ("12", "1", "invalid_postal_code"),
        ("1234ABC", "1", "invalid_postal_code"),
        ("1234AB", "x", "invalid_house_number"),
        ("1234AB", "12a", "invalid_house_number"),
        ("1234AB", "", "invalid_house_number"),
    ],
)
async def test_address_step_shows_the_error_and_keeps_the_input(
    hass, postal_code, house_number, error
):
    """A wrong address shows an error on the same form, with what was typed."""
    result = await _start(hass, "mijnafvalwijzer")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _address(postal_code, house_number)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "address"
    assert result["errors"] == {"base": error}
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_address_step_can_be_corrected_after_an_error(hass):
    """After an error, a valid address creates the entry."""
    result = await _start(hass, "mijnafvalwijzer")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _address("12", "1")
    )
    assert result["errors"] == {"base": "invalid_postal_code"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _address("1234AB", "1")
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_belgian_collector_needs_a_street_and_a_four_digit_postal_code(hass):
    """RecycleApp asks for the street name, and takes a Belgian postal code."""
    result = await _start(hass, "recycleapp")
    assert CONF_STREET_NAME in {str(key) for key in result["data_schema"].schema}

    wrong = await hass.config_entries.flow.async_configure(
        result["flow_id"], _address("1234AB", "1", **{CONF_STREET_NAME: "Tuinstraat"})
    )
    assert wrong["errors"] == {"base": "invalid_postal_code"}

    result = await hass.config_entries.flow.async_configure(
        wrong["flow_id"], _address("9090", "1", **{CONF_STREET_NAME: " Tuinstraat "})
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STREET_NAME] == "Tuinstraat"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "recycleapp:9090:1::Tuinstraat"


async def test_the_same_address_cannot_be_added_twice(hass):
    """An address that is already configured aborts the flow."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "rova",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
        unique_id="rova:1234AB:1",
    ).add_to_hass(hass)
    result = await _start(hass, "rova")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _address("1234AB", "1")
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_refuses_an_unknown_collector(hass):
    """Typed text that is no collector gives a form error, not a new entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_COLLECTOR: "nonexistent"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_COLLECTOR: "invalid_collector"}


# --- import from configuration.yaml ---------------------------------------------------


def _imported(**extra):
    return {
        CONF_COLLECTOR: "mijnafvalwijzer",
        CONF_POSTAL_CODE: "1234 ab",
        CONF_HOUSE_NUMBER: "1",
        CONF_SUFFIX: "b",
        **extra,
    }


async def test_import_creates_an_entry(hass):
    """A valid YAML configuration becomes a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=_imported()
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_POSTAL_CODE] == "1234AB"
    assert result["data"][CONF_SUFFIX] == "B"
    assert result["options"][CONF_EXCLUDE_PICKUP_TODAY] is False


@pytest.mark.parametrize(("exclude", "include"), [(True, False), (False, True)])
async def test_import_converts_the_legacy_exclude_pickup_today_option(
    hass, exclude, include
):
    """The old option excludes today; the entry stores the opposite as include."""
    data = _imported(**{CONF_EXCLUDE_PICKUP_TODAY: exclude})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=data
    )

    assert result["options"][CONF_INCLUDE_TODAY] is include
    assert result["options"][CONF_EXCLUDE_PICKUP_TODAY] is exclude


@pytest.mark.parametrize(
    "bad",
    [
        {CONF_POSTAL_CODE: "12"},
        {CONF_HOUSE_NUMBER: "12a"},
        {CONF_HOUSE_NUMBER: ""},
    ],
)
async def test_import_with_an_invalid_address_aborts(hass, bad):
    """YAML with a wrong address is refused."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data={**_imported(), **bad}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_address"


async def test_import_of_an_existing_address_aborts(hass):
    """Importing the same YAML again doesn't add a second entry."""
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=_imported()
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=_imported()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


# --- options flow ---------------------------------------------------------------------


async def test_options_flow_rejects_a_default_label_that_is_a_date(hass):
    """A default label that looks like a date would be read as a pickup date."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "rova",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_LABEL: "2026-11-17"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_default_label_date"}


async def test_options_flow_cleans_the_options(hass):
    """The exclude list is lowercased, an empty label falls back, and so on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COLLECTOR: "rova",
            CONF_POSTAL_CODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_EXCLUDE_LIST: "GFT, Papier",
            CONF_DEFAULT_LABEL: "  niets ",
            CONF_INCLUDE_TODAY: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EXCLUDE_LIST] == "gft, papier"
    assert result["data"][CONF_DEFAULT_LABEL] == "niets"
    assert result["data"][CONF_EXCLUDE_PICKUP_TODAY] is True


# --- helpers --------------------------------------------------------------------------


def test_clean_user_input_normalizes_the_address():
    """Postal code without spaces in capitals, suffix in capitals, street trimmed."""
    cleaned = _clean_user_input(
        {
            CONF_POSTAL_CODE: " 1234 ab ",
            CONF_SUFFIX: " a ",
            CONF_STREET_NAME: " Dorpsstraat ",
            CONF_FRIENDLY_NAME: "Thuis",
        }
    )

    assert cleaned == {
        CONF_POSTAL_CODE: "1234AB",
        CONF_SUFFIX: "A",
        CONF_STREET_NAME: "Dorpsstraat",
        CONF_FRIENDLY_NAME: "Thuis",
    }


def test_clean_user_input_fills_in_missing_values():
    """Missing optional values become empty strings."""
    cleaned = _clean_user_input({})

    assert cleaned[CONF_POSTAL_CODE] == ""
    assert cleaned[CONF_SUFFIX] == ""
    assert cleaned[CONF_STREET_NAME] == ""


def test_clean_options_input_defaults():
    """Nothing given: an empty exclude list, the default label, today not excluded."""
    cleaned = _clean_options_input({})

    assert cleaned[CONF_EXCLUDE_LIST] == ""
    assert cleaned[CONF_DEFAULT_LABEL] == "geen"
    assert cleaned[CONF_EXCLUDE_PICKUP_TODAY] is False


@pytest.mark.parametrize(
    ("cleaned", "expected"),
    [
        (
            {
                CONF_COLLECTOR: "rova",
                CONF_POSTAL_CODE: "1234AB",
                CONF_HOUSE_NUMBER: "1",
            },
            "rova:1234AB:1",
        ),
        (
            {
                CONF_COLLECTOR: "rova",
                CONF_POSTAL_CODE: "1234AB",
                CONF_HOUSE_NUMBER: "1",
                CONF_SUFFIX: "A",
            },
            "rova:1234AB:1:A",
        ),
        (
            {
                CONF_COLLECTOR: "recycleapp",
                CONF_POSTAL_CODE: "9090",
                CONF_HOUSE_NUMBER: "1",
                CONF_STREET_NAME: "Tuinstraat",
            },
            "recycleapp:9090:1::Tuinstraat",
        ),
    ],
)
def test_unique_id(cleaned, expected):
    """The unique id identifies the collector and the whole address."""
    assert _unique_id_from(cleaned) == expected
