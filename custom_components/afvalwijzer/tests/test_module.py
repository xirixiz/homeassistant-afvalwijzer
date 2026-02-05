"""Sensor component for AfvalWijzer.

Author: Bram van Dartel - xirixiz

Usage:
from afvalwijzer.collector.main_collector import MainCollector
MainCollector('<provider>','<postal_code>','<street_number>','<suffix>','True','True','geen')

Run test:
- Update this file with your information (or the information you would like to test with, examples are in that file)
- Then run `python3 -m afvalwijzer.tests.test_module` from this path <some dir>/homeassistant-afvalwijzer/custom_components
"""

import argparse
import logging
import os

# skip init, required for this test module
os.environ["AFVALWIJZER_SKIP_INIT"] = "1"
from ..collector.main_collector import MainCollector
from .test_data import TEST_ADDRESSES

# Common parameters for all tests
exclude_pickup_today = "False"
exclude_list = ""
default_label = "geen"

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger(__name__)


def _run_for_entry(entry: dict, failures_only: bool = True) -> None:
    provider = entry.get("provider")
    postal_code = entry.get("postal_code").strip().upper()
    street_number = entry.get("street_number")
    suffix = entry.get("suffix", "")

    LOGGER.info(
        "--- Running provider: %s, postal_code: %s, street_number: %s ---",
        provider,
        postal_code,
        street_number,
    )

    collector = MainCollector(
        provider,
        postal_code,
        street_number,
        suffix,
        exclude_pickup_today,
        exclude_list,
        default_label,
    )

    if collector.waste_data_with_today == {} or collector.waste_types_provider == []:
        LOGGER.error(
            "Failed to fetch waste data for provider: %s, postal_code: %s, street_number: %s",
            provider,
            postal_code,
            street_number,
        )
        return

    if failures_only:
        return

    LOGGER.info("Waste data with today: %s", collector.waste_data_with_today)
    LOGGER.info("Waste data without today: %s", collector.waste_data_without_today)
    LOGGER.info("Waste data custom: %s", collector.waste_data_custom)
    LOGGER.info("Waste types provider: %s", collector.waste_types_provider)
    LOGGER.info("Waste types custom: %s", collector.waste_types_custom)
    LOGGER.info("Waste notification data: %s", collector.notification_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test AfvalWijzer collectors")
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Only report failures, skip success logs",
    )
    args = parser.parse_args()

    for entry in TEST_ADDRESSES:
        try:
            _run_for_entry(entry, failures_only=args.failures_only)
        except Exception as exc:  # pragma: no cover - manual test runner
            LOGGER.exception("Error while running entry %s: %s", entry, exc)
