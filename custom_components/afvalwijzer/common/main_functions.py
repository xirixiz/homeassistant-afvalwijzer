"""Common helper functions for the Afvalwijzer integration.

This module provides small, reusable helpers for normalizing user input (postal
codes) and mapping provider-specific waste type labels to standardized keys.
"""

from __future__ import annotations

import re

from ..const.const import _LOGGER
from .postal_code_mappings import get_postal_code_override

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


def waste_type_rename(item_name: str, postal_code: str | None = None) -> str:
    """Normalize a provider waste type label to a standardized key.

    When *postal_code* is supplied, postal-code-specific overrides (defined in
    ``postal_code_mappings.py``) are checked **first**. If a match is found the
    override wins; otherwise the global ``WASTE_TYPE_MAPPING`` is consulted.

    Args:
        item_name: Raw waste type label as provided by a collector/provider.
        postal_code: Optional full postal code (e.g. ``"7941AB"``). Only the
            first four digits are used for the override lookup.

    Returns:
        A standardized waste type key (lowercase). If no mapping exists, return
        the cleaned input.

    """
    cleaned_item_name = item_name.strip().lower()

    # Check postal-code-specific overrides first.
    if postal_code:
        match = POSTAL_CODE_PATTERN.search(postal_code)
        if match:
            postal_code_digits = int(match.group(1))
            override = get_postal_code_override(postal_code_digits, cleaned_item_name)
            if override is not None:
                return override

    waste_type = WASTE_TYPE_MAPPING.get(cleaned_item_name, cleaned_item_name)

    if waste_type not in WASTE_TYPE_MAPPING.values():
        _LOGGER.debug("Unmapped waste type encountered: '%s'", cleaned_item_name)

    return waste_type
