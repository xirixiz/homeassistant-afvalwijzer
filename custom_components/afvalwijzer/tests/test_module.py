"""Sensor component for AfvalWijzer.

Author: Bram van Dartel - xirixiz

Usage:
from afvalwijzer.collector.main_collector import MainCollector
MainCollector('<provider>','<postal_code>','<street_number>','<suffix>','True','True','','geen')

Run test:
- Update this file with your information (or the information you would like to test with, examples are in that file)
- Then run `python3 -m afvalwijzer.tests.test_module` from this path <some dir>/homeassistant-afvalwijzer/custom_components
"""

import logging
import os

# skip init, required for this test module
os.environ["AFVALWIJZER_SKIP_INIT"] = "1"
from ..collector.main_collector import MainCollector

# Common parameters for all tests
exclude_pickup_today = "True"
date_isoformat = "True"
exclude_list = ""
default_label = "geen"

providers = [
    {
        "provider": "acv",
        "enabled": True,
        "addresses": [
            {"postal_code": "6713CG", "street_number": "11"},
            {"postal_code": "6714KK", "street_number": "20"},
        ],
    },
    {
        "provider": "afvalalert",
        "enabled": False,
        "addresses": [
            {"postal_code": "7881NW", "street_number": "4"},
        ],
    },
    {
        "provider": "afvalstoffendienst",
        "enabled": False,
        "addresses": [
            {"postal_code": "4266NB", "street_number": "1"},
        ],
    },
    {
        "provider": "almere",
        "enabled": False,
        "addresses": [
            {"postal_code": "1311HG", "street_number": "20"},
        ],
    },
    {
        "provider": "amsterdam",
        "enabled": False,
        "addresses": [
            {"postal_code": "1066KC", "street_number": "18"},
        ],
    },
    {
        "provider": "avalex",
        "enabled": False,
        "addresses": [
            {"postal_code": "2611XG", "street_number": "87"},
        ],
    },
    {
        "provider": "circulus",
        "enabled": False,
        "addresses": [
            {"postal_code": "7421AC", "street_number": "1"},
        ],
    },
    {
        "provider": "dar",
        "enabled": False,
        "addresses": [
            {"postal_code": "6532AJ", "street_number": "1"},
        ],
    },
    {
        "provider": "geertruidenberg",
        "enabled": False,
        "addresses": [
            {"postal_code": "4941GZ", "street_number": "283"},
        ],
    },
    {
        "provider": "hvc",
        "enabled": False,
        "addresses": [
            {"postal_code": "1822AL", "street_number": "198"},
        ],
    },
    {
        "provider": "maassluis",
        "enabled": False,
        "addresses": [
            {"postal_code": "3146BL", "street_number": "22"},
        ],
    },
    {
        "provider": "mijnafvalwijzer",
        "enabled": False,
        "addresses": [
            {"postal_code": "5146EG", "street_number": "1"},
            {"postal_code": "3192NC", "street_number": "86"},
            {"postal_code": "5563CM", "street_number": "22"},
            {"postal_code": "5685AB", "street_number": "57"},
            {"postal_code": "3601AC", "street_number": "10"},
            {"postal_code": "3951EN", "street_number": "1"},
            {"postal_code": "3951EB", "street_number": "1"},
            {"postal_code": "3941RK", "street_number": "50", "suffix": "B"},
        ],
    },
    {
        "provider": "nijkerk",
        "enabled": False,
        "addresses": [
            {"postal_code": "3861XJ", "street_number": "1"},
        ],
    },
    {
        "provider": "omrin",
        "enabled": False,
        "addresses": [
            {"postal_code": "9991AB", "street_number": "2"},
            {"postal_code": "3844JP", "street_number": "4"},
            {"postal_code": "3845DE", "street_number": "17"},
            {"postal_code": "8085RT", "street_number": "11"},
        ],
    },
    {
        "provider": "prezero",
        "enabled": False,
        "addresses": [
            {"postal_code": "6665CN", "street_number": "1"},
            {"postal_code": "6822NG", "street_number": "1"},
        ],
    },
    {
        "provider": "rd4",
        "enabled": False,
        "addresses": [
            {"postal_code": "6301ET", "street_number": "6"},
        ],
    },
    {
        "provider": "reinis",
        "enabled": False,
        "addresses": [
            {"postal_code": "3209BS", "street_number": "14"},
        ],
    },
    {
        "provider": "rova",
        "enabled": False,
        "addresses": [
            {"postal_code": "7671BL", "street_number": "2"},
        ],
    },
    {
        "provider": "rmn",
        "enabled": False,
        "addresses": [
            {"postal_code": "3701XK", "street_number": "24"},
            {"postal_code": "3402TA", "street_number": "1"},
        ],
    },
    {
        "provider": "rwm",
        "enabled": False,
        "addresses": [
            {"postal_code": "6105CL", "street_number": "50"},
        ],
    },
    {
        "provider": "saver",
        "enabled": False,
        "addresses": [
            {"postal_code": "4708LS", "street_number": "10"},
        ],
    },
    {
        "provider": "tilburg",
        "enabled": False,
        "addresses": [
            {"postal_code": "5038EC", "street_number": "37"},
        ],
    },
    {
        "provider": "venlo",
        "enabled": False,
        "addresses": [
            {"postal_code": "5922TS", "street_number": "1"},
        ],
    },
    {
        "provider": "veldhoven",
        "enabled": False,
        "addresses": [
            {"postal_code": "5508SB", "street_number": "51"},
        ],
    },
    {
        "provider": "woerden",
        "enabled": False,
        "addresses": [
            {"postal_code": "3446GL", "street_number": "16"},
        ],
    },
]

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _run_for_entry(entry: dict) -> None:
    provider = entry.get("provider")
    postal_code = entry.get("postal_code").strip().upper()
    street_number = entry.get("street_number")
    suffix = entry.get("suffix", "")

    logger.info(
        "\n--- Running provider: %s, postal_code: %s, street_number: %s ---",
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
        date_isoformat,
        exclude_list,
        default_label,
    )

    logger.info("Waste data with today: %s", collector.waste_data_with_today)
    logger.info("Waste data without today: %s", collector.waste_data_without_today)
    logger.info("Waste data custom: %s", collector.waste_data_custom)
    logger.info("Waste types provider: %s", collector.waste_types_provider)
    logger.info("Waste types custom: %s", collector.waste_types_custom)
    logger.info("Waste notifications: %s", collector.notification_data)


if __name__ == "__main__":
    for prov in providers:
        provider_name = prov.get("provider")
        if not prov.get("enabled", True):
            logger.info("Skipping disabled provider: %s", provider_name)
            continue

        for addr in prov.get("addresses", []):
            entry = {"provider": provider_name, **addr}
            try:
                _run_for_entry(entry)
            except Exception as exc:  # pragma: no cover - manual test runner
                logger.exception("Error while running entry %s: %s", entry, exc)
