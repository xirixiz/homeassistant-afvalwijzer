#!/usr/bin/env python3
"""
Sensor component for AfvalDienst
Author: Bram van Dartel - xirixiz

import afvalwijzer
from afvalwijzer.collector.afvalwijzer import AfvalWijzer
AfvalWijzer().get_data('','','')

python3 -m afvalwijzer.testing.test_module

"""

import datetime

from afvalwijzer.collector.afvalwijzer import AfvalWijzerCollector

# from afvalwijzer.collector.afvalwijzer import AfvalWijzer
from afvalwijzer.collector.ximmio import XimmioCollector

# from ..collector.afvalwijzer import AfvalWijzer

provider = "mijnafvalwijzer"

# provider = "afvalstoffendienstkalender"
# api_token = "5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca"

# Afvalstoffendienstkalender
# postal_code = "5391KE"
# street_number = "1"

# Afvalwijzer
postal_code = "5146EG"
street_number = "6"

suffix = ""
include_date_today = "False"
default_label = "Geen"
exclude_list = ""

afvalwijzer = AfvalWijzerCollector(
    provider,
    postal_code,
    street_number,
    suffix,
    default_label,
    exclude_list,
)

provider = "meerlanden"
postal_code = "2201XZ"
street_number = "38"
ximmio = XimmioCollector(
    provider,
    postal_code,
    street_number,
    suffix,
    default_label,
    exclude_list,
)

print(afvalwijzer.waste_data_with_today)
print(ximmio.waste_data_with_today)


# data = XimmioCollector().get_waste_data_provider("meerlanden", postal_code2, street_number2, suffix, default_label, exclude_list)
# data2 = AfvalWijzerCollector().get_waste_data_provider("mijnafvalwijzer", postal_code, street_number, suffix, default_label, exclude_list)


#########################################################################################################
print("\n")

# print(afvalwijzer.waste_data_with_today)
# print(afvalwijzer.waste_data_without_today)
# print(afvalwijzer.waste_data_custom)
# print(afvalwijzer.waste_types_provider)
# print(afvalwijzer.waste_types_custom)

print("\n")

# for key, value in afval1.items():
#     print(key, value)

# print("\n")

# for key, value in afval2.items():
#     print(key, value)
