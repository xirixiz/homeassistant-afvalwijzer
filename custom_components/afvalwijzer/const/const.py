import logging
from datetime import timedelta

SENSOR_PROVIDER_TO_URL = {
    "afvalwijzer_scraper_default": ["https://www.{0}.nl/nl/{1}/{2}/{3}/"],
    "afvalwijzer_scraper_rova": ["https://inzamelkalender.{0}.nl/nl/{1}/{2}/{3}/"],
}

MONTH_TO_NUMBER = {
    "jan": "01",
    "feb": "02",
    "mrt": "03",
    "apr": "04",
    "mei": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "okt": "10",
    "nov": "11",
    "dec": "12",
    "januari": "01",
    "februari": "02",
    "maart": "03",
    "april": "04",
    "mei": "05",
    "juni": "06",
    "juli": "07",
    "augustus": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "december": "12",
}

NUMBER_TO_MONTH = {
    1: "januari",
    2: "februari",
    3: "maart",
    4: "april",
    5: "mei",
    6: "juni",
    7: "juli",
    8: "augustus",
    9: "september",
    10: "oktober",
    11: "november",
    12: "december",
}

CONF_PROVIDER = "provider"
CONF_API_TOKEN = (
    "api_token"  # 5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca
)
CONF_POSTAL_CODE = "postal_code"
CONF_STREET_NUMBER = "street_number"
CONF_SUFFIX = "suffix"
CONF_DATE_FORMAT = "date_format"
CONF_INCLUDE_DATE_TODAY = "include_date_today"
CONF_DEFAULT_LABEL = "default_label"
CONF_ID = "id"

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
Version: 5.1.1
This is a custom integration!
If you have any issues with this you need to open an issue here:
"https://github.com/xirixiz/homeassistant-afvalwijzer/issues"
-------------------------------------------------------------------
"""
