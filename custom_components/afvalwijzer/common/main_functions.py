import re

def _waste_type_rename(item_name):
    # Mapping of waste types
    waste_mapping = {
        "branches": "takken",
        "best_bag": "best-tas",
        "bulklitter": "grofvuil",
        "bulkygardenwaste": "tuinafval",
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
        "pmdrest": "pmd-restafval",
        "pmd-zak": "pmd",
        "pruning_waste": "snoeiafval",
        "remainder": "restwagen",
        "residual_waste": "restafval",
        "rest": "restafval",
        "restafvalzakken": "restafvalzakken",
        "rst": "restafval",
        "sloop": "grofvuil",
        "snoeiafval": "takken",
        "tariefzak restafval": "restafvalzakken",
        "textile": "textiel",
        "tree": "kerstbomen",
        "zak_blauw": "restafval",
    }

    return waste_mapping.get(item_name, item_name)

def _clean_type_rename(item_name):
    cleaning_mapping = {
        "rst": "cleaning_restafval",
        "gft": "cleaning_gft",
    }

    return cleaning_mapping.get(item_name, item_name)

def format_postal_code(postal_code: str) -> str:
    match = re.search(r"(\d{4}) ?([A-Za-z]{2})", postal_code)
    if match:
        return f"{match[1]}{match[2].upper()}"
    return postal_code 