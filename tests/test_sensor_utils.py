"""Tests for shared sensor helper functions in common/sensor_utils.py."""

from types import SimpleNamespace

from custom_components.afvalwijzer.common.sensor_utils import translated_type_list

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
