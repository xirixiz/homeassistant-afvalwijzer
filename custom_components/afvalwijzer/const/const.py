import logging
from datetime import timedelta

SENSOR_PROVIDER_TO_URL = {
    "afvalwijzer_data_default": [
        "https://api.{0}.nl/webservices/appsinput/?apikey=5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca&method=postcodecheck&postcode={1}&street=&huisnummer={2}&toevoeging={3}&app_name=afvalwijzer&platform=phone&afvaldata={4}&langs=nl&"
    ],
}

CONF_PROVIDER = "provider"
CONF_API_TOKEN = "api_token"
# 5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca
CONF_POSTAL_CODE = "postal_code"
CONF_STREET_NUMBER = "street_number"
CONF_SUFFIX = "suffix"
CONF_DATE_FORMAT = "date_format"
CONF_INCLUDE_DATE_TODAY = "include_date_today"
CONF_DEFAULT_LABEL = "default_label"
CONF_ID = "id"
CONF_EXCLUDE_LIST = "exclude_list"

SENSOR_PREFIX = "afvalwijzer "
SENSOR_ICON = "mdi:recycle"

ATTR_LAST_UPDATE = "last_update"
ATTR_HIDDEN = "hidden"
ATTR_IS_COLLECTION_DATE_TODAY = "is_collection_date_today"
ATTR_IS_COLLECTION_DATE_TOMORROW = "is_collection_date_tomorrow"
ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW = "is_collection_date_day_after_tomorrow"
ATTR_DAYS_UNTIL_COLLECTION_DATE = "days_until_collection_date"
ATTR_YEAR_MONTH_DAY_DATE = "year_month_day_date"

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=30)

DOMAIN = "afvalwijzer"
DOMAIN_DATA = "afvalwijzer_data"

STARTUP_MESSAGE = """
-------------------------------------------------------------------
Afvalwijzer
Version: 5.3.3
This is a custom integration!
If you have any issues with this you need to open an issue here:
"https://github.com/xirixiz/homeassistant-afvalwijzer/issues"
-------------------------------------------------------------------
"""
