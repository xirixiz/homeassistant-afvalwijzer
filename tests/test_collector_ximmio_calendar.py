"""Tests for the Ximmio full-calendar support."""

from custom_components.afvalwijzer.collector import ximmio


def test_all_pickup_dates_are_returned():
    """Every pickup date of a stream is kept, not only the next one."""
    data = {
        "dataList": [
            {
                "_pickupTypeText": "GREEN",
                "pickupDates": [
                    "2026-10-19T00:00:00",
                    "2026-10-05T00:00:00",
                    "2026-11-02T00:00:00",
                ],
            },
            {"_pickupTypeText": "PAPER", "pickupDates": ["2026-10-12T00:00:00"]},
        ]
    }

    assert ximmio._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-10-05"},
        {"type": "gft", "date": "2026-10-19"},
        {"type": "gft", "date": "2026-11-02"},
        {"type": "papier", "date": "2026-10-12"},
    ]


def test_invalid_and_duplicate_dates_are_skipped():
    """An unparseable date costs only itself, and duplicates collapse."""
    data = {
        "dataList": [
            {
                "_pickupTypeText": "GREEN",
                "pickupDates": [
                    "2026-10-05T00:00:00",
                    "garbage",
                    "",
                    "2026-10-05T00:00:00",
                    "2026-10-19",
                ],
            }
        ]
    }

    assert ximmio._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-10-05"},
        {"type": "gft", "date": "2026-10-19"},
    ]


def test_streams_without_dates_are_skipped():
    """A stream without pickup dates adds nothing."""
    data = {"dataList": [{"_pickupTypeText": "GREEN", "pickupDates": []}, "junk"]}

    assert ximmio._parse_waste_data_raw(data) == []
