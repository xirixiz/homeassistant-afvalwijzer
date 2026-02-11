"""Common helper functions for the Afvalwijzer integration.

This module provides small, reusable helpers for normalizing user input (postal
codes) and mapping provider-specific waste type labels to standardized keys.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..const.const import _LOGGER

# Precompile the postal code pattern for better performance.
POSTAL_CODE_PATTERN = re.compile(r"(\d{4})\s*([A-Za-z]{2})")

WASTE_TYPE_MAPPING: dict[str, str] = {
    "best": "best-tas",
    "best_bag": "best-tas",
    "bestafr": "best-tas",
    "bio-afval": "gft",
    "biobak": "gft",
    "biobak op afroep": "gft",
    "branches": "snoeiafval",
    "bulklitter": "grofvuil",
    "bulkygardenwaste": "tuinafval",
    "bulkyrestwaste": "pmd-restafval",
    "chemisch afval": "kca",
    "chemokar": "kca",
    "christmas_trees": "kerstbomen",
    "container restafval": "restafval",
    "ga": "grofvuil",
    "gemengde plastics": "plastic",
    "gft": "gft",
    "gft & etensresten": "gft",
    "gft afval": "gft",
    "gft en etensresten": "gft",
    "gft groente- fruit en tuinafval": "gft",
    "gft+e": "gft",
    "gft-afval": "gft",
    "gfte": "gft",
    "gfte afval": "gft",
    "glass": "glas",
    "green": "gft",
    "grey": "restafval",
    "grijze container": "restafval",
    "grijze container / sortibak": "restafval",
    "groene container": "gft",
    "groene container / biobak": "gft",
    "groente": "gft",
    "groente, fruit en tuinafval + etensresten": "gft",
    "groente, fruit en tuinafval en etensresten": "gft",
    "groente, fruit en tuinafval en etensresten.": "gft",
    "groente, fruit- en tuinafval": "gft",
    "groente,- fruit,- tuinafval en etensresten": "gft",
    "groente-, fruit en tuinafval": "gft",
    "groente-, fruit- en tuinafval": "gft",
    "groente-, fruit- en tuinafval  en etensresten (gft+e)": "gft",
    "groente-, fruit- en tuinafval (gft)": "gft",
    "groenten, fruit, tuin en etensresten": "gft",
    "grof": "grofvuil",
    "grof tuinafval": "snoeiafval",
    "grofvuil": "grofvuil",
    "grofvuil en elektrische apparaten": "grofvuil",
    "inzameling gft en etensresten": "gft",
    "inzameling gft+e": "gft",
    "inzameling papier en karton": "papier",
    "inzameling plastic, blik en drankenkartons": "pmd",
    "kca klein chemisch afval": "kca",
    "kerstb": "kerstbomen",
    "kerstboom": "kerstbomen",
    "luiers": "luiers",
    "opk": "papier",
    "oud papier": "papier",
    "oud papier & karton": "papier",
    "oud papier en karton": "papier",
    "oud papier huis aan huis inzameling pkn de westereen": "papier",
    "packages": "pmd",
    "packagesbag": "pmd",
    "pap": "papier",
    "paper": "papier",
    "papier": "papier",
    "papier (overdag)": "papier",
    "papier door remondis": "papier",
    "papier en karton": "papier",
    "papier en karton (avond inzameling)": "papier",
    "papier en karton (inzameling overdag)": "papier",
    "papier en karton eemnes": "papier",
    "papier-karton": "papier",
    "papiercont": "papier",
    "papierinzameling": "papier",
    "pbd": "pmd",
    "pbp": "pmd",
    "pd": "pmd",
    "pdb": "pmd",
    "plastic": "plastic",
    "plastic en blik/ drankkartons": "pmd",
    "plastic verpakkingen, metaal en drankenkartons (pmd)": "pmd",
    "plastic verpakkingen, metalen verpakkingen en drinkpakken": "pmd",
    "plastic+": "plastic",
    "plastic, blik & drankkartons": "pmd",
    "plastic, blik & drinkpakken": "pmd",
    "plastic, blik & drinkpakken arnhem": "pmd",
    "plastic, blik & drinkpakken eemnes": "pmd",
    "plastic, blik & drinkpakken overbetuwe": "pmd",
    "plastic, blik en drankkartons": "pmd",
    "plastic, blik en drinkpakken": "pmd",
    "plastic, metaal en drankenkartons": "pmd",
    "plastic, metaal en drankkartons": "pmd",
    "plastic, metaal en drinkpakken": "pmd",
    "plastic, metalen en drankkartons (pmd)": "pmd",
    "plastic, metalen verpakkingen en drankkartons": "pmd",
    "pmd in zakken": "pmd",
    "pmd plastic, metalen en drankkartons": "pmd",
    "pmd+": "pmd",
    "pmd-zak": "pmd",
    "pmdrest": "pmd-restafval",
    "pruning_waste": "snoeiafval",
    "remainder": "restwagen",
    "residual_waste": "restafval",
    "rest": "restafval",
    "restafval in zak": "restafvalzakken",
    "restafval- mini containers": "restafval",
    "restafvalzakken": "restafvalzakken",
    "rolcontainer gft en etensresten": "gft",
    "rolcontainer restafval": "restafval",
    "rst": "restafval",
    "sloop": "grofvuil",
    "sortibak": "sorti",
    "takken": "snoeiafval",
    "takken en snoeiafval": "snoeiafval",
    "tariefzak restafval": "restafvalzakken",
    "textile": "textiel",
    "tree": "kerstbomen",
    "verpakking van plastic, blik en drinkpakken": "pmd",
    "zak_blauw": "restafval",
}


def format_postal_code(postal_code: str) -> str:
    """Format a Dutch postal code as `1234AB`.

    Args:
        postal_code: Input postal code, optionally containing spaces and lowercase letters.

    Returns:
        The formatted postal code (e.g. `1234AB`). If the input does not match the expected
        Dutch format, return the original value unchanged.

    """
    match = POSTAL_CODE_PATTERN.search(postal_code)
    if not match:
        return postal_code
    return f"{match.group(1)}{match.group(2).upper()}"


def normalize_custom_mapping(custom_mapping: dict[str, str] | None) -> dict[str, str]:
    """Normalize a custom mapping to lowercase string keys and values."""
    if not custom_mapping:
        return {}

    normalized: dict[str, str] = {}
    for key, value in custom_mapping.items():
        if key is None or value is None:
            continue

        key_clean = str(key).strip().lower()
        value_clean = str(value).strip().lower()
        if not key_clean or not value_clean:
            continue

        normalized[key_clean] = value_clean

    return normalized


def parse_custom_mapping(raw: Any) -> dict[str, str]:
    """Parse a custom mapping from a dict or JSON string."""
    if not raw:
        return {}

    if isinstance(raw, dict):
        return normalize_custom_mapping(raw)

    if isinstance(raw, str):
        raw_str = raw.strip()
        if not raw_str:
            return {}

        try:
            parsed = json.loads(raw_str)
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid custom mapping JSON provided; ignoring.")
            return {}

        if not isinstance(parsed, dict):
            _LOGGER.warning("Custom mapping JSON must be an object; ignoring.")
            return {}

        return normalize_custom_mapping(parsed)

    _LOGGER.warning("Custom mapping must be a dict or JSON string; ignoring.")
    return {}


def waste_type_rename(
    item_name: str, custom_mapping: dict[str, str] | None = None
) -> str:
    """Normalize a provider waste type label to a standardized key.

    Args:
        item_name: Raw waste type label as provided by a collector/provider.
        custom_mapping: Optional mapping raw labels to standardized keys. Custom
            mapping takes precedence over built-in mappings.

    Returns:
        A standardized waste type key (lowercase). If no mapping exists, return the
        cleaned input.

    """
    cleaned_item_name = item_name.strip().lower()

    custom_mapping = parse_custom_mapping(custom_mapping)
    if cleaned_item_name in custom_mapping:
        return custom_mapping[cleaned_item_name]

    waste_type = WASTE_TYPE_MAPPING.get(cleaned_item_name, cleaned_item_name)

    if waste_type not in WASTE_TYPE_MAPPING.values():
        _LOGGER.debug("Unmapped waste type encountered: '%s'", cleaned_item_name)

    return waste_type
