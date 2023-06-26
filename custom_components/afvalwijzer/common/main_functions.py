def _waste_type_rename(item_name):
    # BURGERPORTAAL
    if item_name == "rest":
        item_name = "restafval"
    if item_name == "opk":
        item_name = "papier"
    if item_name == 'pmdrest':
        item_name = "pmd-restafval"
    if item_name == "rest":
        item_name = "restafval"
    # DEAFVALAPP
    if item_name == "gemengde plastics":
        item_name = "plastic"
    if item_name == "zak_blauw":
        item_name = "restafval"
    if item_name == "pbp":
        item_name = "pmd"
    if item_name == "rest":
        item_name = "restafval"
    if item_name == "kerstboom":
        item_name = "kerstbomen"
    # OPZET
    if item_name == "snoeiafval":
        item_name = "takken"
    if item_name == "sloop":
        item_name = "grofvuil"
    if item_name == "groente":
        item_name = "gft"
    if item_name == "groente-, fruit en tuinafval":
        item_name = "gft"
    if item_name == "groente, fruit- en tuinafval":
        item_name = "gft"
    if item_name == "kca":
        item_name = "chemisch"
    if item_name == "tariefzak restafval":
        item_name = "restafvalzakken"
    if item_name == "restafvalzakken":
        item_name = "restafvalzakken"
    if item_name == "rest":
        item_name = "restafval"
    if item_name == "plastic, blik & drinkpakken overbetuwe":
        item_name = "pmd"
    if item_name == "plastic, blik & drinkpakken arnhem":
        item_name = "pmd"
    if item_name == "papier en karton":
        item_name = "papier"
    if item_name == "kerstb":
        item_name = "kerstboom"
    # RD4
    if item_name == "pruning_waste":
        item_name = "snoeiafval"
    if item_name == "pruning_waste":
        item_name = "takken"
    if item_name == "residual_waste":
        item_name = "restafval"
    if item_name == "best_bag":
        item_name = "best-tas"
    if item_name == "paper":
        item_name = "papier"
    if item_name == "christmas_trees":
        item_name = "kerstbomen"
    # XIMMIO
    if item_name == "branches":
        item_name = "takken"
    if item_name == "bulklitter":
        item_name = "grofvuil"
    if item_name == "bulkygardenwaste":
        item_name = "tuinafval"
    if item_name == "glass":
        item_name = "glas"
    if item_name == "green":
        item_name = "gft"
    if item_name == "grey":
        item_name = "restafval"
    if item_name == "kca":
        item_name = "chemisch"
    if item_name == "plastic":
        item_name = "plastic"
    if item_name == "packages":
        item_name = "pmd"
    if item_name == "paper":
        item_name = "papier"
    if item_name == "remainder":
        item_name = "restwagen"
    if item_name == "textile":
        item_name = "textiel"
    if item_name == "tree":
        item_name = "kerstbomen"
    return item_name


if __name__ == "__main__":
    print("Yell something at a mountain!")
