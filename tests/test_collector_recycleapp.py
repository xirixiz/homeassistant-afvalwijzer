"""Tests for the RecycleApp collector."""

import pytest

from custom_components.afvalwijzer.collector import recycleapp


def _item(timestamp: str) -> dict:
    return {
        "timestamp": timestamp,
        "fraction": {"name": {"nl": "Restafval"}},
    }


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-05T00:00:00.000Z",
        "2026-10-05T00:00:00.123Z",
        "2026-10-05T00:00:00Z",
        "2026-10-05T00:00:00.5Z",
        "2026-10-05T00:00:00+00:00",
    ],
)
def test_timestamp_variants_are_parsed(timestamp):
    """Timestamps with and without fractional seconds give the same date."""
    result = recycleapp._parse_waste_data_raw({"items": [_item(timestamp)]})

    assert result == [{"type": "restafval", "date": "2026-10-05"}]
