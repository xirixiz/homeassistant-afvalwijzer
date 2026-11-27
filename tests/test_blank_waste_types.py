"""A pickup whose type is blank carries no information and is left out everywhere."""

import pytest

from custom_components.afvalwijzer.collector import (
    amsterdam,
    burgerportaal,
    circulus,
    deafvalapp,
    irado,
    montferland,
    recycleapp,
    reinis,
    straatbeeld,
)
from custom_components.afvalwijzer.common.main_functions import (
    parse_ical_waste_data,
    waste_type_rename,
)

BLANKS = ["", " ", "\t"]


@pytest.mark.parametrize("blank", BLANKS)
def test_a_blank_label_maps_to_nothing(blank):
    """The mapping gives an empty type for a blank label, which callers skip."""
    assert waste_type_rename(blank) == ""


@pytest.mark.parametrize("blank", BLANKS)
def test_circulus_skips_a_blank_code(blank):
    """A garbage entry without a code gives no pickups."""
    data = [
        {"code": blank, "dates": ["2026-11-13"]},
        {"code": "gft", "dates": ["2026-11-20"]},
    ]

    assert circulus._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-11-20"}
    ]


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_burgerportaal_skips_a_blank_fraction(blank):
    """A fraction of only spaces is as good as none."""
    data = [
        {"collectionDate": "2026-11-13T00:00:00", "fraction": blank},
        {"collectionDate": "2026-11-20T00:00:00", "fraction": "gft"},
    ]

    assert burgerportaal._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-11-20"}
    ]


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_deafvalapp_skips_a_row_with_a_blank_type(blank):
    """A row that starts with spaces is skipped, the next row is read."""
    text = f"{blank};13-11-2026;\ngft;20-11-2026;\n"

    assert deafvalapp._parse_waste_data_raw(text) == [
        {"type": "gft", "date": "2026-11-20"}
    ]


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_irado_skips_a_blank_type(blank):
    """A pickup with a type of only spaces is dropped."""
    day = [{"date": "13/11/2026", "type": blank}, {"date": "20/11/2026", "type": "gft"}]
    data = {"valid": True, "calendar_data": {"pickups": {"2026": {"11": {"1": day}}}}}

    assert irado._parse_waste_data_raw(data) == [{"type": "gft", "date": "2026-11-20"}]


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_recycleapp_skips_a_blank_name(blank):
    """A fraction whose name is only spaces is dropped."""
    data = {
        "items": [
            {
                "timestamp": "2026-11-13T00:00:00.000Z",
                "fraction": {"name": {"nl": blank}},
            },
            {
                "timestamp": "2026-11-20T00:00:00.000Z",
                "fraction": {"name": {"nl": "GFT"}},
            },
        ]
    }

    assert recycleapp._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-11-20"}
    ]


def test_amsterdam_skips_a_blank_fraction_code():
    """A fraction code of only spaces gives no pickups."""
    item = {
        "afvalwijzerFractieCode": "  ",
        "afvalwijzerAfvalkalenderFrequentie": "x",
    }

    assert amsterdam._parse_waste_data_raw([item]) == []


def test_straatbeeld_skips_a_blank_type():
    """A calendar entry whose type is only spaces gives no pickups."""
    day = {
        "date": {"formatted": "2026-11-13"},
        "data": [{"name": "  "}, {"name": "GFT"}],
    }
    data = {"collections": {"2026": {"11": [day]}}}

    assert straatbeeld._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-11-13"}
    ]


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_ical_events_with_a_blank_summary_are_skipped(blank):
    """An event without a summary gives no pickup, instead of one without a type."""
    text = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
        f"SUMMARY:{blank}\r\nDTSTART;VALUE=DATE:20261113\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nSUMMARY:GFT\r\nDTSTART;VALUE=DATE:20261120\r\nEND:VEVENT\r\n"
        "END:VCALENDAR"
    )

    assert parse_ical_waste_data(text) == [{"type": "gft", "date": "2026-11-20"}]


def _nothing(*_args):
    return ""


def test_irado_skips_a_type_that_maps_to_nothing(monkeypatch):
    """A pickup whose type maps to nothing is dropped."""
    monkeypatch.setattr(irado, "waste_type_rename", _nothing)
    day = [{"date": "20/11/2026", "type": "gft"}]
    data = {"valid": True, "calendar_data": {"pickups": {"2026": {"11": {"1": day}}}}}

    assert irado._parse_waste_data_raw(data) == []


def test_montferland_skips_a_type_that_maps_to_nothing(monkeypatch):
    """A collection whose type maps to nothing is dropped."""
    monkeypatch.setattr(montferland, "waste_type_rename", _nothing)
    data = {
        "errorCode": 0,
        "collections": [{"fraction": 2, "collectionDate": "2026-11-20T00:00:00"}],
    }

    assert montferland._parse_waste_data_raw(data) == []


def test_reinis_skips_a_type_that_maps_to_nothing(monkeypatch):
    """A pickup whose type maps to nothing is dropped."""
    monkeypatch.setattr(reinis, "waste_type_rename", _nothing)
    days = [{"pickups": [{"date": "2026-11-20", "streamId": "gft"}]}]

    assert reinis._parse_waste_data_raw(days) == []


def test_amsterdam_skips_a_type_that_maps_to_nothing(monkeypatch):
    """An item whose type maps to nothing gives no pickups."""
    monkeypatch.setattr(amsterdam, "waste_type_rename", _nothing)
    item = {
        "afvalwijzerFractieCode": "GFT",
        "afvalwijzerOphaaldagen": "vrijdag",
        "afvalwijzerAfvalkalenderFrequentie": "05-03-27",
    }

    assert amsterdam._parse_waste_data_raw([item]) == []
