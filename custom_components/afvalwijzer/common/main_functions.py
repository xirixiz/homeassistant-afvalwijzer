"""Afvalwijzer integration."""

import re

POSTAL_CODE_PATTERN = re.compile(r"(\d{4})\s*([A-Za-z]{2})")


def format_postal_code(postal_code: str) -> str:
    """Format a postal code string.

    Remove spaces and convert letters to uppercase.

    Args:
        postal_code: The input postal code.

    Returns:
        A formatted postal code (for example "1234AB"). If no match is found,
        return the original string.

    """
    match = POSTAL_CODE_PATTERN.search(postal_code)
    if match:
        return f"{match.group(1)}{match.group(2).upper()}"
    return postal_code


def waste_type_rename(item_name: str) -> str:
    """Rename a waste type to a standardized value.

    Clean the input value and map it to a standardized waste type when possible.

    Args:
        item_name: The original waste type string.

    Returns:
        The standardized waste type.

    """
    cleaned_item_name = item_name.strip().lower()

    waste_mapping = {
        "branches": "takken",
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
        "gft+e": "gft",
        "green": "gft",
        "groene container": "gft",
        "groente": "gft",
        "groente-, fruit en tuinafval": "gft",
        "groente, fruit- en tuinafval": "gft",
        "groente, fruit en tuinafval + etensresten": "gft",
        "grof tuinafval": "takken",
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
        "snoeiafval": "takken",
        "tariefzak restafval": "restafvalzakken",
        "textile": "textiel",
        "tree": "kerstbomen",
        "zak_blauw": "restafval",
    }

    return waste_mapping.get(cleaned_item_name, cleaned_item_name)
