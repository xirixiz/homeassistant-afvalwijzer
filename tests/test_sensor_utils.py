"""Tests for shared sensor helper functions in common/sensor_utils.py."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from custom_components.afvalwijzer import _load_sensor_translations
from custom_components.afvalwijzer.common import sensor_utils
from custom_components.afvalwijzer.common.sensor_utils import (
    address_key,
    address_label,
    as_utc_aware,
    build_device_info,
    date_to_local_midnight,
    icon_for_waste_type,
    initial_color_for_waste_type,
    is_naive,
    make_unique_id,
    normalize_waste_type_key,
    parse_and_apply_value,
    translated_type_list,
)
from custom_components.afvalwijzer.const.const import (
    CONF_COLLECTOR,
    CONF_FRIENDLY_NAME,
    CONF_HOUSE_NUMBER,
    CONF_POSTAL_CODE,
    CONF_STREET_NAME,
    CONF_SUFFIX,
    DOMAIN,
)

_TRANSLATIONS = {
    "gft": {"name": "GFT"},
    "papier": {"name": "Paper"},
    "geen": {"name": "None"},
    "best_tas": {"name": "BEST-bag"},
}


def _coordinator(translations=None):
    return SimpleNamespace(sensor_translations=translations or _TRANSLATIONS)


def test_translated_type_list_single_value():
    """A single known waste type is translated."""
    assert translated_type_list("gft", _coordinator()) == ["GFT"]


def test_translated_type_list_composite_value():
    """Comma-joined values are split and each part translated independently."""
    assert translated_type_list("gft, papier", _coordinator()) == ["GFT", "Paper"]
    # No space after the comma is handled the same way.
    assert translated_type_list("gft,papier", _coordinator()) == ["GFT", "Paper"]


def test_translated_type_list_normalizes_case_and_hyphens():
    """Lookup is case-insensitive and hyphens/spaces normalize like the keys do."""
    assert translated_type_list("GFT", _coordinator()) == ["GFT"]
    assert translated_type_list("best-tas", _coordinator()) == ["BEST-bag"]


def test_translated_type_list_unmapped_falls_back_to_original():
    """A type without a translation entry keeps its original text."""
    assert translated_type_list("unknown_type", _coordinator()) == ["unknown_type"]


def test_translated_type_list_default_label():
    """The default_label value (e.g. 'geen') translates like any other entry."""
    assert translated_type_list("geen", _coordinator()) == ["None"]


def test_translated_type_list_default_label_pinned_to_real_translation_data():
    """The 'geen' -> 'None' translation holds against the real shipped JSON.

    entity.sensor.geen has no translation_key pointing at it (those come
    from waste types, not default_label) - its only consumer is this
    lookup, reached indirectly. Without this, the entry could be deleted
    as apparently-dead and translated_types would silently start
    reporting ["geen"] with no test failing.
    """
    coordinator = SimpleNamespace(sensor_translations=_load_sensor_translations("en"))
    assert translated_type_list("geen", coordinator) == ["None"]


def test_translated_type_list_custom_default_label_with_comma_not_split():
    """A custom default_label containing a comma is kept as one part, not fragmented.

    default_label is free text, not a list of waste types - splitting it on
    comma would produce bogus entries that don't match the sensor's actual
    (unsplit) state.
    """
    label = "Niets gepland, geen"
    assert translated_type_list(label, _coordinator(), default_label=label) == [label]


def test_translated_type_list_composite_value_with_comma_in_default_label_configured():
    """Real comma-joined waste type data still splits even when default_label is set."""
    assert translated_type_list(
        "gft, papier", _coordinator(), default_label="Niets gepland, geen"
    ) == ["GFT", "Paper"]


def test_translated_type_list_ignores_reserved_sensor_kind_keys():
    """A waste type that collides with a reserved entity-name key isn't mistranslated.

    entity.sensor.* also carries HA's own entity-name translations for
    sensor kinds like "notifications" or "next_type" - those must never be
    picked up as if they were a waste-type translation.
    """
    translations = _coordinator(
        {**_TRANSLATIONS, "notifications": {"name": "Notifications"}}
    )
    assert translated_type_list("notifications", translations) == ["notifications"]


def test_translated_type_list_none_and_empty():
    """None and empty-string values return None rather than an empty list."""
    assert translated_type_list(None, _coordinator()) is None
    assert translated_type_list("", _coordinator()) is None


def test_translated_type_list_non_string_returns_none():
    """Non-string values (e.g. a date already parsed upstream) return None."""
    assert translated_type_list(123, _coordinator()) is None


def test_translated_type_list_missing_coordinator_translations():
    """A coordinator without sensor_translations degrades to raw text, not an error."""
    coordinator = SimpleNamespace()
    assert translated_type_list("gft", coordinator) == ["gft"]


# --- icons, colors and keys ---------------------------------------------------------


def test_icon_and_color_of_a_waste_type():
    """Known types have an icon and a color; unknown ones use the default."""
    assert icon_for_waste_type("gft") is not None
    assert icon_for_waste_type("nonexistent") is None
    assert icon_for_waste_type("nonexistent", "mdi:delete") == "mdi:delete"
    assert initial_color_for_waste_type("kerstbomen") == "#1B5E20"
    assert initial_color_for_waste_type("nonexistent") is None


def test_normalize_waste_type_key():
    """Keys are lower case with underscores."""
    assert normalize_waste_type_key("Best-Tas") == "best_tas"


# --- time zones ---------------------------------------------------------------------


def test_is_naive():
    """A datetime without a usable offset is naive."""
    assert is_naive(datetime(2026, 11, 13))
    assert not is_naive(datetime(2026, 11, 13, tzinfo=UTC))


def test_a_naive_datetime_is_read_in_the_home_assistant_time_zone():
    """Naive local time is converted to UTC through the configured zone."""
    with patch.object(
        sensor_utils.dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Europe/Amsterdam")
    ):
        assert as_utc_aware(datetime(2026, 11, 13, 12, 0)) == datetime(
            2026, 11, 13, 11, 0, tzinfo=UTC
        )


def test_an_aware_datetime_is_only_converted_to_utc():
    """The zone of an aware datetime is kept as it is."""
    value = datetime(2026, 7, 1, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

    assert as_utc_aware(value) == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)


def test_date_to_local_midnight():
    """A date becomes midnight in the Home Assistant time zone."""
    zone = ZoneInfo("Europe/Amsterdam")
    with patch.object(sensor_utils.dt_util, "DEFAULT_TIME_ZONE", zone):
        result = date_to_local_midnight(date(2026, 11, 13))

    assert result == datetime(2026, 11, 13, tzinfo=zone)
    assert result.tzinfo is zone


# --- address, id and device ---------------------------------------------------------

ADDRESS = {
    CONF_COLLECTOR: "mijnafvalwijzer",
    CONF_POSTAL_CODE: " 1234 ab ",
    CONF_HOUSE_NUMBER: " 5 ",
    CONF_SUFFIX: " b ",
    CONF_STREET_NAME: " Teststraat ",
}


def test_address_key_is_normalized():
    """Case, spaces and empty parts don't change the key."""
    assert address_key(ADDRESS) == "1234AB:5:B:Teststraat"
    assert (
        address_key({CONF_POSTAL_CODE: "1234AB", CONF_HOUSE_NUMBER: "5"}) == "1234AB:5"
    )


def test_address_label_is_readable():
    """The label is postal code, number with suffix and street."""
    assert address_label(ADDRESS) == "1234AB 5B Teststraat"
    assert (
        address_label({CONF_POSTAL_CODE: "1234AB", CONF_HOUSE_NUMBER: "5"})
        == "1234AB 5"
    )


def test_unique_id_depends_on_the_type_the_collector_and_the_address():
    """The id is stable, and changes with each of its parts."""
    unique_id = make_unique_id(ADDRESS, "gft")

    assert unique_id == make_unique_id(dict(ADDRESS), "gft")
    assert len(unique_id) == 40
    assert unique_id != make_unique_id(ADDRESS, "papier")
    assert unique_id != make_unique_id({**ADDRESS, CONF_COLLECTOR: "rova"}, "gft")
    assert unique_id != make_unique_id({**ADDRESS, CONF_HOUSE_NUMBER: "6"}, "gft")


def test_device_info_groups_the_sensors_of_an_address():
    """The device is named after the friendly name, or else the address."""
    plain = build_device_info(ADDRESS)
    named = build_device_info({**ADDRESS, CONF_FRIENDLY_NAME: "Thuis"})

    assert plain["identifiers"] == {(DOMAIN, "1234AB:5:B:Teststraat")}
    assert plain["name"] == "Afvalwijzer 1234AB 5B Teststraat"
    assert named["name"] == "Afvalwijzer Thuis"
    assert plain["model"] == "mijnafvalwijzer"
    assert plain["manufacturer"] == "Afvalwijzer"


# --- values -------------------------------------------------------------------------


def test_parse_and_apply_value():
    """Date and datetime strings are parsed; everything else is kept.

    A date-only string is already read as a datetime (midnight) by Home Assistant's
    datetime parser, so the date parser behind it is never needed.
    """
    assert parse_and_apply_value("2026-11-13T12:30:00") == (
        datetime(2026, 11, 13, 12, 30),
        None,
    )
    assert parse_and_apply_value("2026-11-13") == (datetime(2026, 11, 13), None)
    assert parse_and_apply_value("gft") == ("gft", None)
    assert parse_and_apply_value(5) == (5, None)
    assert parse_and_apply_value(None) == (None, None)
