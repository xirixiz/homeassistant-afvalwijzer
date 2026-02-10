"""Sensor component for AfvalWijzer.

Author: Bram van Dartel - xirixiz

Usage:
from afvalwijzer.collector.main_collector import MainCollector
MainCollector('<provider>','<postal_code>','<house_number>','<suffix>','True','True','geen')

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

# Common parameters for all tests
exclude_pickup_today = "False"
exclude_list = ""
default_label = "geen"

# fmt: off
addresses = [
    {"provider": "acv", "postal_code": "6713CG", "house_number": "11"},
    {"provider": "acv", "postal_code": "6714KK", "house_number": "20"},
    {"provider": "afval3xbeter", "postal_code": "4874AA", "house_number": "42"},
    {"provider": "afvalstoffendienst", "postal_code": "5222AA", "house_number": "5"},
    {"provider": "afvalstoffendienstkalender", "postal_code": "5237BE", "house_number": "2"},
    {"provider": "almere", "postal_code": "1311HG", "house_number": "20"},
    {"provider": "alphenaandenrijn", "postal_code": "2408CV", "house_number": "5"},
    {"provider": "amsterdam", "postal_code": "1066KC", "house_number": "18"},
    {"provider": "areareiniging", "postal_code": "7812PC", "house_number": "107"},
    {"provider": "assen", "postal_code": "9403XT", "house_number": "19"},
    {"provider": "avalex", "postal_code": "2611XG", "house_number": "87"},
    {"provider": "avri", "postal_code": "4191LE", "house_number": "24"},
    {"provider": "bar", "postal_code": "3161XB", "house_number": "13", "suffix": "b"},
    {"provider": "blink", "postal_code": "5741MD", "house_number": "24"},
    {"provider": "circulus", "postal_code": "7421AC", "house_number": "1"},
    {"provider": "cranendonck", "postal_code": "6021XV", "house_number": "25"},
    {"provider": "cyclus", "postal_code": "2805GG", "house_number": "25"},
    {"provider": "dar", "postal_code": "6532AJ", "house_number": "1"},
    {"provider": "dar", "postal_code": "6665CN", "house_number": "1"},
    {"provider": "deafvalapp", "postal_code": "5708TE", "house_number": "2"},
    {"provider": "defryskemarren", "postal_code": "8501BR", "house_number": "21"},
    {"provider": "denhaag", "postal_code": "2564EX", "house_number": "75"},
    {"provider": "gad", "postal_code": "1214HA", "house_number": "156"},
    {"provider": "geertruidenberg", "postal_code": "4941GZ", "house_number": "283"},
    {"provider": "groningen", "postal_code": "9725KL", "house_number": "5"},
    {"provider": "hellendoorn", "postal_code": "7447BA", "house_number": "11"},
    {"provider": "hvc", "postal_code": "1822AL", "house_number": "198"},
    {"provider": "irado", "postal_code": "3114VC", "house_number": "23"},
    {"provider": "lingewaard", "postal_code": "6851JW", "house_number": "15"},
    {"provider": "maassluis", "postal_code": "3146BL", "house_number": "22"},
    {"provider": "meerlanden", "postal_code": "2162JP", "house_number": "2"},
    {"provider": "middelburg-vlissingen", "postal_code": "4335SW", "house_number": "36"},
    {"provider": "middelburg-vlissingen", "postal_code": "4388KD", "house_number": "198"},
    {"provider": "mijnafvalwijzer", "postal_code": "3192NC", "house_number": "86"},
    {"provider": "mijnafvalwijzer", "postal_code": "3601AC", "house_number": "10"},
    {"provider": "mijnafvalwijzer", "postal_code": "3941RK", "house_number": "50", "suffix": "B"},
    {"provider": "mijnafvalwijzer", "postal_code": "3951EB", "house_number": "1"},
    {"provider": "mijnafvalwijzer", "postal_code": "3951EN", "house_number": "1"},
    {"provider": "mijnafvalwijzer", "postal_code": "5146EG", "house_number": "1"},
    {"provider": "mijnafvalwijzer", "postal_code": "5563CM", "house_number": "22"},
    {"provider": "mijnafvalwijzer", "postal_code": "5685AB", "house_number": "57"},
    {"provider": "mijnafvalwijzer", "postal_code": "7944AB", "house_number": "1"},
    {"provider": "mijnafvalzaken", "postal_code": "1901XG", "house_number": "7"},
    {"provider": "montferland", "postal_code": "7041EJ", "house_number": "13"},
    {"provider": "montfoort", "postal_code": "3461CV", "house_number": "10"},
    {"provider": "nijkerk", "postal_code": "3861XJ", "house_number": "1"},
    {"provider": "offalkalinder", "postal_code": "9853PR", "house_number": "12"},
    {"provider": "omrin", "postal_code": "3844JP", "house_number": "4"},
    {"provider": "omrin", "postal_code": "3845DE", "house_number": "17"},
    {"provider": "omrin", "postal_code": "8085RT", "house_number": "11"},
    {"provider": "omrin", "postal_code": "9991AB", "house_number": "2"},
    {"provider": "oudeijsselstreek", "postal_code": "7081GD", "house_number": "79"},
    {"provider": "peelenmaas", "postal_code": "5991GR", "house_number": "32"},
    {"provider": "prezero", "postal_code": "6822NG", "house_number": "1"},
    {"provider": "purmerend", "postal_code": "1462XP", "house_number": "11"},
    {"provider": "rad", "postal_code": "3252BV", "house_number": "17"},
    {"provider": "rd4", "postal_code": "6301ET", "house_number": "6"},
    {"provider": "reinis", "postal_code": "3209BS", "house_number": "14"},
    {"provider": "rmn", "postal_code": "3402TA", "house_number": "1"},
    {"provider": "rmn", "postal_code": "3701XK", "house_number": "24"},
    {"provider": "rova", "postal_code": "7671BL", "house_number": "2"},
    {"provider": "rwm", "postal_code": "6105CL", "house_number": "50"},
    {"provider": "saver", "postal_code": "4708LS", "house_number": "10"},
    {"provider": "schouwen-duiveland", "postal_code": "4301SH", "house_number": "2"},
    {"provider": "sliedrecht", "postal_code": "3362ND", "house_number": "52"},
    {"provider": "spaarnelanden", "postal_code": "2025AE", "house_number": "148"},
    {"provider": "straatbeeld", "postal_code": "4921AH", "house_number": "8"},
    {"provider": "sudwestfryslan", "postal_code": "8604ED", "house_number": "1"},
    {"provider": "tilburg", "postal_code": "5038EC", "house_number": "37"},
    {"provider": "twentemilieu", "postal_code": "7524AR", "house_number": "3"},
    {"provider": "uithoorn", "postal_code": "1422KL", "house_number": "24"},
    {"provider": "venlo", "postal_code": "5922TS", "house_number": "1"},
    {"provider": "venray", "postal_code": "5802AC", "house_number": "12"},
    {"provider": "voorschoten", "postal_code": "2251JA", "house_number": "10"},
    {"provider": "waalre", "postal_code": "5583AS", "house_number": "15"},
    {"provider": "waardlanden", "postal_code": "4143GD", "house_number": "46"},
    {"provider": "woerden", "postal_code": "3446GL", "house_number": "16"},
    {"provider": "ximmio", "postal_code": "2162JP", "house_number": "2"},
    {"provider": "zrd", "postal_code": "4561MT", "house_number": "3"},
]
# fmt: on

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger(__name__)


def _run_for_entry(entry: dict, show_failures_only: bool = False) -> None:
    provider = entry.get("provider")
    postal_code = entry.get("postal_code").strip().upper()
    house_number = entry.get("house_number")
    suffix = entry.get("suffix", "")

    LOGGER.info(
        "--- Running provider: %s, postal_code: %s, house_number: %s ---",
        provider,
        postal_code,
        house_number,
    )

    collector = MainCollector(
        provider,
        postal_code,
        house_number,
        suffix,
        exclude_pickup_today,
        exclude_list,
        default_label,
    )

    if collector.waste_data_with_today == {} or collector.waste_types_provider == []:
        LOGGER.error(
            "Failed to fetch waste data for provider: %s, postal_code: %s, house_number: %s",
            provider,
            postal_code,
            house_number,
        )
        return

    if show_failures_only:
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
        "--show-failures-only",
        action="store_true",
        help="Only report failures, skip success logs",
    )
    args = parser.parse_args()

    for entry in addresses:
        try:
            _run_for_entry(entry, args.show_failures_only)
        except Exception as exc:  # pragma: no cover - manual test runner
            LOGGER.exception("Error while running entry %s: %s", entry, exc)
