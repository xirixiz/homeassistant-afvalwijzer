"""Tests for the Rova date parsing."""

import pytest

from custom_components.afvalwijzer.collector import rova


@pytest.mark.parametrize(
    "date",
    ["2026-10-05T00:00:00Z", "2026-10-05T00:00:00+00:00", "2026-10-05T00:00:00+02:00"],
)
def test_rova_accepts_any_utc_offset(date):
    """Rova dates are parsed whatever offset notation the API uses."""
    data = [{"wasteType": {"title": "GFT"}, "date": date}]

    assert rova._parse_waste_data_raw(data) == [{"type": "gft", "date": "2026-10-05"}]
