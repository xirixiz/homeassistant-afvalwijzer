#!/usr/bin/env python3
"""
Sensor component for AfvalDienst
Author: Bram van Dartel - xirixiz

import afvalwijzer
from afvalwijzer.provider.afvalwijzer import AfvalWijzer
AfvalWijzer().get_data('','','')

python3 -m afvalwijzer.test_sensor

"""

provider = "mijnafvalwijzer"

# provider = "afvalstoffendienstkalender"
# api_token = "5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca"

# Afvalstoffendienstkalender
# postal_code = "5391KE"
# street_number = "1"

# Afvalwijzer
# postal_code = "5146EG"
# street_number = "1"

postal_code = "4707PB"
street_number = "110"

# Rova
# provider = "rova"
# postal_code = "3824XB"
# street_number = "2"


# postal_code = "4714CB"
# street_number = "57"

# postal_code = "5473VD"
# street_number = "7"

# postal_code = "6691XX"
# street_number = "22"

suffix = ""
include_date_today = "False"
default_label = "Geen"
exclude_list = "gft"

from .provider.afvalwijzer import AfvalWijzer

afvalwijzer = AfvalWijzer(
    provider,
    postal_code,
    street_number,
    suffix,
    include_date_today,
    default_label,
    exclude_list,
)

#########################################################################################################
print("\n")

print(afvalwijzer.waste_data_with_today)
print(afvalwijzer.waste_data_without_today)
print(afvalwijzer.waste_data_custom)
print(afvalwijzer.waste_types_provider)
print(afvalwijzer.waste_types_custom)

print("\n")

# for key, value in afval1.items():
#     print(key, value)

# print("\n")

# for key, value in afval2.items():
#     print(key, value)
