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

# Common parameters for all tests
exclude_pickup_today = "False"
exclude_list = ""
default_label = "geen"

# fmt: off
addresses = [
    #{"provider": "acv", "postal_code": "6713CG", "street_number": "11"},
    #{"provider": "acv", "postal_code": "6714KK", "street_number": "20"},
    #{"provider": "afval3xbeter", "postal_code": "4874AA", "street_number": "42"},
    #{"provider": "afvalstoffendienst", "postal_code": "5222AA", "street_number": "5"},
    #{"provider": "afvalstoffendienst", "postal_code": "5237BE", "street_number": "2"},
    #{"provider": "almere", "postal_code": "1311HG", "street_number": "20"},
    #{"provider": "alphenaandenrijn", "postal_code": "2408CV", "street_number": "5"},
    #{"provider": "amsterdam", "postal_code": "1066KC", "street_number": "18"},
    #{"provider": "areareiniging", "postal_code": "7812PC", "street_number": "107"},
    #{"provider": "assen", "postal_code": "9403XT", "street_number": "19"},
    #{"provider": "avalex", "postal_code": "2611XG", "street_number": "87"},
    #{"provider": "avri", "postal_code": "4191LE", "street_number": "24"},
    #{"provider": "bar", "postal_code": "3161XB", "street_number": "13", "suffix": "b"},
    #{"provider": "blink", "postal_code": "5741MD", "street_number": "24"},
    #{"provider": "circulus", "postal_code": "7421AC", "street_number": "1"},
    #{"provider": "cranendonck", "postal_code": "6021XV", "street_number": "25"},
    #{"provider": "cyclus", "postal_code": "2805GG", "street_number": "25"},
    #{"provider": "dar", "postal_code": "6532AJ", "street_number": "1"},
    #{"provider": "dar", "postal_code": "6665CN", "street_number": "1"},
    #{"provider": "deafvalapp", "postal_code": "5708TE", "street_number": "2"},
    #{"provider": "defryskemarren", "postal_code": "8501BR", "street_number": "21"},
    #{"provider": "denhaag", "postal_code": "2564EX", "street_number": "75"},
    #{"provider": "gad", "postal_code": "1214HA", "street_number": "156"},
    #{"provider": "geertruidenberg", "postal_code": "4941GZ", "street_number": "283"},
    #{"provider": "groningen", "postal_code": "9725KL", "street_number": "5"},
    #{"provider": "hellendoorn", "postal_code": "7447BA", "street_number": "11"},
    #{"provider": "hvc", "postal_code": "1822AL", "street_number": "198"},
    #{"provider": "irado", "postal_code": "3114VC", "street_number": "23"},
    #{"provider": "lingewaard", "postal_code": "6851JW", "street_number": "15"},
    #{"provider": "maassluis", "postal_code": "3146BL", "street_number": "22"},
    #{"provider": "meerlanden", "postal_code": "2162JP", "street_number": "2"},
    #{"provider": "middelburg-vlissingen", "postal_code": "4335SW", "street_number": "36"},
    #{"provider": "middelburg-vlissingen", "postal_code": "4388KD", "street_number": "198"},
    #{"provider": "mijnafvalwijzer", "postal_code": "3192NC", "street_number": "86"},
    #{"provider": "mijnafvalwijzer", "postal_code": "3601AC", "street_number": "10"},
    #{"provider": "mijnafvalwijzer", "postal_code": "3941RK", "street_number": "50", "suffix": "B"},
    #{"provider": "mijnafvalwijzer", "postal_code": "3951EB", "street_number": "1"},
    #{"provider": "mijnafvalwijzer", "postal_code": "3951EN", "street_number": "1"},
    #{"provider": "mijnafvalwijzer", "postal_code": "5146EG", "street_number": "1"},
    #{"provider": "mijnafvalwijzer", "postal_code": "5563CM", "street_number": "22"},
    #{"provider": "mijnafvalwijzer", "postal_code": "5685AB", "street_number": "57"},
    #{"provider": "mijnafvalwijzer", "postal_code": "7944AB", "street_number": "1"},
    #{"provider": "mijnafvalzaken", "postal_code": "1901XG", "street_number": "7"},
    #{"provider": "montferland", "postal_code": "7041EJ", "street_number": "13"},
    #{"provider": "montfoort", "postal_code": "3461CV", "street_number": "10"},
    #{"provider": "nijkerk", "postal_code": "3861XJ", "street_number": "1"},
    #{"provider": "offalkalinder", "postal_code": "9853PR", "street_number": "12"},
    #{"provider": "omrin", "postal_code": "3844JP", "street_number": "4"},
    #{"provider": "omrin", "postal_code": "3845DE", "street_number": "17"},
    #{"provider": "omrin", "postal_code": "8085RT", "street_number": "11"},
    #{"provider": "omrin", "postal_code": "9991AB", "street_number": "2"},
    #{"provider": "oudeijsselstreek", "postal_code": "7081GD", "street_number": "79"},
    #{"provider": "peelenmaas", "postal_code": "5991GR", "street_number": "32"},
    #{"provider": "prezero", "postal_code": "6822NG", "street_number": "1"},
    #{"provider": "purmerend", "postal_code": "1462XP", "street_number": "11"},
    #{"provider": "rad", "postal_code": "3252BV", "street_number": "17"},
    #{"provider": "rd4", "postal_code": "6301ET", "street_number": "6"},
    #{"provider": "reinis", "postal_code": "3209BS", "street_number": "14"},
    #{"provider": "rmn", "postal_code": "3402TA", "street_number": "1"},
    #{"provider": "rmn", "postal_code": "3701XK", "street_number": "24"},
    #{"provider": "rova", "postal_code": "7671BL", "street_number": "2"},
    #{"provider": "rwm", "postal_code": "6105CL", "street_number": "50"},
    #{"provider": "saver", "postal_code": "4708LS", "street_number": "10"},
    #{"provider": "schouwen-duiveland", "postal_code": "4301SH", "street_number": "2"},
    #{"provider": "sliedrecht", "postal_code": "3362ND", "street_number": "52"},
    #{"provider": "spaarnelanden", "postal_code": "2025AE", "street_number": "148"},
    #{"provider": "straatbeeld", "postal_code": "4921AH", "street_number": "8"},
    #{"provider": "sudwestfryslan", "postal_code": "8604ED", "street_number": "1"},
    #{"provider": "tilburg", "postal_code": "5038EC", "street_number": "37"},
    #{"provider": "twentemilieu", "postal_code": "7524AR", "street_number": "3"},
    #{"provider": "uithoorn", "postal_code": "1422KL", "street_number": "24"},
    #{"provider": "venlo", "postal_code": "5922TS", "street_number": "1"},
    #{"provider": "venray", "postal_code": "5802AC", "street_number": "12"},
    #{"provider": "voorschoten", "postal_code": "2251JA", "street_number": "10"},
    #{"provider": "waalre", "postal_code": "5583AS", "street_number": "15"},
    #{"provider": "waardlanden", "postal_code": "4143GD", "street_number": "46"},
    #{"provider": "woerden", "postal_code": "3446GL", "street_number": "16"},
    #{"provider": "ximmio", "postal_code": "2162JP", "street_number": "2"},
    #{"provider": "zrd", "postal_code": "4561MT", "street_number": "3"},
]
# fmt: on

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger(__name__)


def _run_for_entry(entry: dict, show_failures_only: bool = False) -> None:
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
