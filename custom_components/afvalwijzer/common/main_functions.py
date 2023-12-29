def _waste_type_rename(item_name):
    mapping = {
        "rest": "restafval",
        "opk": "papier",
        "pmdrest": "pmd-restafval",
        "gemengde plastics": "plastic",
        "zak_blauw": "restafval",
        "pbp": "pmd",
        "kerstboom": "kerstbomen",
        "snoeiafval": "takken",
        "sloop": "grofvuil",
        "groente": "gft",
        "groente-, fruit en tuinafval": "gft",
        "groente, fruit- en tuinafval": "gft",
        "tariefzak restafval": "restafvalzakken",
        "restafvalzakken": "restafvalzakken",
        "plastic, blik & drinkpakken overbetuwe": "pmd",
        "plastic, blik & drinkpakken arnhem": "pmd",
        "papier en karton": "papier",
        "kerstb": "kerstboom",
        "pruning_waste": "takken",
        "residual_waste": "restafval",
        "best_bag": "best-tas",
        "christmas_trees": "kerstbomen",
        "branches": "takken",
        "bulklitter": "grofvuil",
        "bulkygardenwaste": "tuinafval",
        "glass": "glas",
        "green": "gft",
        "grey": "restafval",
        "kca": "chemisch",
        "plastic": "plastic",
        "pdb": "pmd",
        "packages": "pmd",
        "paper": "papier",
        "remainder": "restwagen",
        "textile": "textiel",
        "tree": "kerstbomen",
    }
    return mapping.get(item_name, item_name)


if __name__ == "__main__":
    print("Yell something at a mountain!")
