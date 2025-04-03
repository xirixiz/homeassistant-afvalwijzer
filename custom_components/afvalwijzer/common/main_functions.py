import re

# Precompile the postal code pattern for better performance
POSTAL_CODE_PATTERN = re.compile(r"(\d{4})\s*([A-Za-z]{2})")

def format_postal_code(postal_code: str) -> str:
    """
    Formats a postal code string by removing any spaces and converting letters to uppercase.

    Parameters:
        postal_code (str): The input postal code.

    Returns:
        str: A formatted postal code (e.g., "1234AB"). If no match is found, returns the original string.
    """
    match = POSTAL_CODE_PATTERN.search(postal_code)
    if match:
        return f"{match.group(1)}{match.group(2).upper()}"
    return postal_code

def waste_type_rename(item_name: str) -> str:
    """
    Cleans and renames the waste type based on a mapping dictionary.

    It removes escape sequences and anything after a '/', then trims and lowercases the result
    before mapping it to the standardized waste type.

    Parameters:
        item_name (str): The original waste type string.

    Returns:
        str: The standardized waste type.
    """
    # Remove escape sequences and text after '/'
    cleaned_item_name = item_name.strip().lower()

    # Mapping of waste types to standardized names
    waste_mapping = {
        "branches": "takken",
        "best_bag": "best-tas",
        "bulklitter": "grofvuil",
        "bulkygardenwaste": "tuinafval",
        "bulkyrestwaste": "pmd-restafval",
        "chemokar": "chemisch",
        "christmas_trees": "kerstbomen",
        "gemengde plastics": "plastic",
        "gft & etensresten": "gft",
        "glass": "glas",
        "gft afval": "gft",
        "gft+e": "gft",
        "green": "gft",
        "groene container": "gft",
        "groente": "gft",
        "groente-, fruit en tuinafval": "gft",
        "groente, fruit- en tuinafval": "gft",
        "grof tuinafval": "takken",
        "grey": "restafval",
        "grijze container": "restafval",
        "kca": "chemisch",
        "kerstb": "kerstboom",
        "kerstboom": "kerstbomen",
        "opk": "papier",
        "packages": "pmd",
        "pap": "papier",
        "paper": "papier",
        "pbd": "pmd",
        "pdb": "pmd",
        "papier en karton": "papier",
        "papierinzameling": "papier",
        "papier en karton (inzameling overdag)": "papier",
        "papier en karton (avond inzameling)": "papier",
        "plastic": "plastic",
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
        "snoeiafval": "takken",
        "tariefzak restafval": "restafvalzakken",
        "textile": "textiel",
        "tree": "kerstbomen",
        "zak_blauw": "restafval",
    }

    return waste_mapping.get(cleaned_item_name, cleaned_item_name)

def secondary_type_rename(item_name):

        # Remove escape sequences and text after '/'
    cleaned_item_name = item_name.strip().lower()

    auxiliary_mapping = {
        "rst": "secondary_restafval",
        "gft": "secondary_gft",
    }

    return auxiliary_mapping.get(cleaned_item_name, item_name)