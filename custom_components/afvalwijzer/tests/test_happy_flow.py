"""Happy-flow tests for Afvalwijzer using mocked provider responses."""

from datetime import datetime, timedelta
from unittest.mock import patch

from custom_components.afvalwijzer.collector.main_collector import MainCollector


def test_main_collector_happy_flow():
    """MainCollector should process provider data and expose transformed results."""
    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    sample_raw = [
        {"type": "restafval", "date": today},
        {"type": "papier", "date": next_week},
    ]

    with patch(
        "custom_components.afvalwijzer.collector.mijnafvalwijzer.get_waste_data_raw",
        return_value=sample_raw,
    ):
        collector = MainCollector(
            "mijnafvalwijzer",
            "1234AB",
            "1",
            "",
            "False",
            "",
            "geen",
        )

        types = [t.lower() for t in collector.waste_types_provider]
        assert "restafval" in types
        assert "papier" in types

        provider_data = collector.waste_data_provider
        assert "restafval" in provider_data
        assert provider_data["restafval"] != "geen"
        assert isinstance(collector.notification_data, list)
