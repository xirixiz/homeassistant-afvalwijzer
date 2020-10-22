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
api_token = "5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca"
api_token2 = ""
postal_code = "5146EG"
street_number = "1"
suffix = ""
include_date_today = "False"
default_label = "Geen"

from .provider.afvalwijzer import AfvalWijzer

# afval1 = AfvalWijzer(provider, api_token, postal_code, street_number, suffix, include_date_today, default_label)
afval2 = AfvalWijzer(
    provider,
    api_token2,
    postal_code,
    street_number,
    suffix,
    include_date_today,
    default_label,
)

#########################################################################################################
# print("\n")

# print(afval1.waste_data_provider)
# print(afval1.waste_data_custom)
# print(afval1.waste_types_provider)
# print(afval1.waste_types_custom)

print("\n")

print(afval2.waste_data_provider)
print(afval2.waste_data_custom)
print(afval2.waste_types_provider)
print(afval2.waste_types_custom)

print("\n")

# for key, value in afval1.items():
#     print(key, value)

# print("\n")

# for key, value in afval2.items():
#     print(key, value)
