"""Tests for the shared helpers in common/main_functions.py."""

import logging
from unittest.mock import patch

import pytest

from custom_components.afvalwijzer.common.main_functions import (
    format_postal_code,
    parse_ical_waste_data,
    waste_type_rename,
)


def _calendar(*events):
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", *events, "END:VCALENDAR"])


def _event(summary=None, dtstart=None, *extra):
    lines = ["BEGIN:VEVENT", *extra]
    if summary is not None:
        lines.append(f"SUMMARY:{summary}")
    if dtstart is not None:
        lines.append(dtstart)
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


# --- iCal ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", None])
def test_ical_without_text_gives_nothing(text):
    """Nothing to parse."""
    assert parse_ical_waste_data(text) == []


def test_ical_events_become_dates_and_standard_waste_types():
    """Summaries as the providers write them are mapped to the usual types."""
    text = _calendar(
        _event("Grijze container", "DTSTART;VALUE=DATE:20261113"),
        _event("Groene container", "DTSTART;VALUE=DATE:20261120"),
        _event("Papierinzameling", "DTSTART;VALUE=DATE:20261127"),
        _event("Kerstboom", "DTSTART;VALUE=DATE:20270108"),
    )

    assert parse_ical_waste_data(text) == [
        {"type": "restafval", "date": "2026-11-13"},
        {"type": "gft", "date": "2026-11-20"},
        {"type": "papier", "date": "2026-11-27"},
        {"type": "kerstbomen", "date": "2027-01-08"},
    ]


def test_ical_summary_is_trimmed_and_lowercased():
    """The case and spacing of the provider don't matter for the mapping."""
    text = _calendar(_event("  GROENE Container  ", "DTSTART;VALUE=DATE:20261113"))

    assert parse_ical_waste_data(text) == [{"type": "gft", "date": "2026-11-13"}]


def test_ical_unknown_summary_is_kept_as_is():
    """A type we don't know stays visible, lowercase, instead of disappearing."""
    text = _calendar(_event("Wintertuin", "DTSTART;VALUE=DATE:20261113"))

    assert parse_ical_waste_data(text) == [{"type": "wintertuin", "date": "2026-11-13"}]


@pytest.mark.parametrize(
    "dtstart",
    [
        "DTSTART;VALUE=DATE:20261113",
        "DTSTART:20261113",
        "DTSTART;TZID=Europe/Amsterdam:20261113T060000",
    ],
)
def test_ical_start_with_or_without_parameters_and_time(dtstart):
    """The date is the first eight digits, whatever follows."""
    text = _calendar(_event("Groene container", dtstart))

    assert parse_ical_waste_data(text) == [{"type": "gft", "date": "2026-11-13"}]


def test_ical_accepts_unix_line_endings_and_ignores_other_lines():
    """Calendar properties, other event properties and lines without a colon are skipped."""
    text = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "X-WR-CALNAME:Afvalkalender: Goes",
            "SUMMARY:Not an event",
            "a line that is not a property",
            "BEGIN:VEVENT",
            "UID:abc",
            "DESCRIPTION:Zet de container buiten: voor 07:00",
            "SUMMARY:Grijze container",
            "DTSTART;VALUE=DATE:20261113",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )

    assert parse_ical_waste_data(text) == [{"type": "restafval", "date": "2026-11-13"}]


def test_ical_event_without_a_summary_is_dropped_and_does_not_reuse_the_last_one(
    caplog,
):
    """Each event starts empty: a missing summary is not filled in from the event before."""
    text = _calendar(
        _event("Grijze container", "DTSTART;VALUE=DATE:20261113"),
        _event(None, "DTSTART;VALUE=DATE:20261120"),
    )

    with caplog.at_level(logging.WARNING):
        result = parse_ical_waste_data(text)

    assert result == [{"type": "restafval", "date": "2026-11-13"}]
    assert "Incomplete iCal event data" in caplog.text


def test_ical_event_without_a_date_is_dropped(caplog):
    """An event needs both a type and a date."""
    text = _calendar(_event("Grijze container", None))

    with caplog.at_level(logging.WARNING):
        assert parse_ical_waste_data(text) == []
    assert "Incomplete iCal event data" in caplog.text


@pytest.mark.parametrize(
    "dtstart", ["DTSTART:vrijdag", "DTSTART:2026-11-13", "DTSTART:2026"]
)
def test_ical_unsupported_date_format_is_reported(dtstart, caplog):
    """A date we can't read is reported, and its event is dropped."""
    text = _calendar(_event("Grijze container", dtstart))

    with caplog.at_level(logging.WARNING):
        assert parse_ical_waste_data(text) == []
    assert "Unsupported waste_date format" in caplog.text


def test_ical_forwards_the_postal_code_for_overrides():
    """A postal code specific mapping wins over the general one."""
    text = _calendar(_event("Grijze container", "DTSTART;VALUE=DATE:20261113"))

    with patch(
        "custom_components.afvalwijzer.common.main_functions.get_postal_code_override",
        return_value="sorti",
    ) as override:
        result = parse_ical_waste_data(text, "4464BW")

    assert result == [{"type": "sorti", "date": "2026-11-13"}]
    override.assert_called_once_with(4464, "grijze container")


# --- postal codes and waste types ---------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1234AB", "1234AB"),
        ("1234 ab", "1234AB"),
        (" 1234  aB ", "1234AB"),
        ("1234", "1234"),  # a Belgian postal code has no letters
        ("abc", "abc"),
        ("", ""),
    ],
)
def test_format_postal_code(text, expected):
    """Dutch postal codes are written without a space, in capitals."""
    assert format_postal_code(text) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Groene container", "gft"),
        ("  PAPIER  ", "papier"),
        ("Restafval", "restafval"),
        ("Nog onbekend", "nog onbekend"),
    ],
)
def test_waste_type_rename(name, expected):
    """Known labels are mapped, unknown ones are only cleaned."""
    assert waste_type_rename(name) == expected


def test_waste_type_rename_logs_unmapped_types(caplog):
    """An unmapped label is logged, so it can be added to the mapping."""
    with caplog.at_level(logging.DEBUG):
        waste_type_rename("Nog onbekend")

    assert "Unmapped waste type encountered: 'nog onbekend'" in caplog.text
