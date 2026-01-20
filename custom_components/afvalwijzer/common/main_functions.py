"""Common helper functions for the Afvalwijzer integration.

This module provides small, reusable helpers for normalizing user input (postal
codes) and mapping provider-specific waste type labels to standardized keys.
"""

from __future__ import annotations

import re

# Precompile the postal code pattern for better performance.
POSTAL_CODE_PATTERN = re.compile(r"(\d{4})\s*([A-Za-z]{2})")


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


def waste_type_rename(item_name: str) -> str:
    """Normalize a provider waste type label to a standardized key.

    Args:
        item_name: Raw waste type label as provided by a collector/provider.

    Returns:
        A standardized waste type key (lowercase). If no mapping exists, return the
        cleaned input.

    """
    cleaned_item_name = item_name.strip().lower()

    waste_mapping: dict[str, str] = {
        "branches": "snoeiafval",
        "best_bag": "best-tas",
        "biobak op afroep": "gft",
        "biobak": "gft",
        "bulklitter": "grofvuil",
        "bulkygardenwaste": "tuinafval",
        "bulkyrestwaste": "pmd-restafval",
        "chemisch afval": "kca",
        "chemokar": "chemisch",
        "christmas_trees": "kerstbomen",
        "gemengde plastics": "plastic",
        "gft": "gft",
        "gft & etensresten": "gft",
        "glass": "glas",
        "gft afval": "gft",
        "gfte afval": "gft",
        "gft+e": "gft",
        "green": "gft",
        "groene container": "gft",
        "groente": "gft",
        "groente-, fruit en tuinafval": "gft",
        "groente, fruit- en tuinafval": "gft",
        "groente, fruit en tuinafval + etensresten": "gft",
        "grof tuinafval": "snoeiafval",
        "grofvuil": "grofvuil",
        "grofvuil en elektrische apparaten": "grofvuil",
        "grey": "restafval",
        "grijze container": "restafval",
        "kerstb": "kerstboom",
        "kerstboom": "kerstbomen",
        "opk": "papier",
        "oud papier en karton": "papier",
        "packages": "pmd",
        "packagesbag": "pmd",
        "pap": "papier",
        "paper": "papier",
        "papier": "papier",
        "pbd": "pmd",
        "pdb": "pmd",
        "papier en karton": "papier",
        "papierinzameling": "papier",
        "papier en karton (inzameling overdag)": "papier",
        "papier en karton (avond inzameling)": "papier",
        "plastic": "plastic",
        "plastic, blik & drankkartons": "pmd",
        "plastic, blik & drinkpakken": "pmd",
        "plastic, blik & drinkpakken arnhem": "pmd",
        "plastic, blik & drinkpakken overbetuwe": "pmd",
        "plastic, metaal en drankkartons": "pmd",
        "pmdrest": "pmd-restafval",
        "pmd-zak": "pmd",
        "pruning_waste": "snoeiafval",
        "remainder": "restwagen",
        "residual_waste": "restafval",
        "rest": "restafval",
        "restafval- mini containers": "restafval",
        "restafvalzakken": "restafvalzakken",
        "rst": "restafval",
        "sloop": "grofvuil",
        "sortibak": "sorti",
        "takken en snoeiafval": "snoeiafval",
        "tariefzak restafval": "restafvalzakken",
        "textile": "textiel",
        "tree": "kerstbomen",
        "zak_blauw": "restafval",
    }

    return waste_mapping.get(cleaned_item_name, cleaned_item_name)
