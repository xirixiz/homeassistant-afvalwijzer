# from homeassistant.helpers.event import async_track_point_in_utc_time
# from homeassistant.util import dt as dt_util
# from homeassistant.components import persistent_notification

# from .const import *

from abc import ABC, abstractmethod
import logging
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_LOGGER = logging.getLogger(__name__)

class WasteCollection:
    def __init__(self, date, waste_type):
        self.date = date
        self.waste_type = waste_type

    def __repr__(self):
        return f"<WasteCollection date={self.date} type={self.waste_type}>"

class WasteCollectionRepository:
    def __init__(self):
        self.collections = []

    def __iter__(self):
        yield from self.collections

    def __len__(self):
        return len(self.collections)

    def add(self, collection):
        self.collections.append(collection)

    def remove_all(self):
        self.collections = []

    def get_sorted(self):
        return sorted(self.collections, key=lambda x: x.date)

    def get_upcoming(self):
        today = datetime.now()
        return [x for x in self.get_sorted() if x.date.date() >= today.date()]

    def get_first_upcoming(self, waste_types=None):
        upcoming = self.get_upcoming()
        if not upcoming:
            return None

        first_item_date = upcoming[0].date.date()
        return [x for x in upcoming if x.date.date() == first_item_date and (not waste_types or x.waste_type.lower() in map(str.lower, waste_types))]

    def get_upcoming_by_type(self, waste_type):
        today = datetime.now()
        return [x for x in self.get_sorted() if x.date.date() >= today.date() and x.waste_type.lower() == waste_type.lower()]

    def get_first_upcoming_by_type(self, waste_type):
        upcoming = self.get_upcoming_by_type(waste_type)
        return upcoming[0] if upcoming else None

    def get_by_date(self, date, waste_types=None):
        if not waste_types:
            return [x for x in self.collections if x.date.date() == date.date()]

        return [
            x for x in self.collections
            if x.date.date() == date.date() and x.waste_type.lower() in map(str.lower, waste_types)
        ]

class WasteCollectorBase(ABC):
    @abstractmethod
    def fetch_data(self):
        pass

    @abstractmethod
    def parse_data(self, data):
        pass

class AfvalwijzerCollector(WasteCollectorBase):
    def __init__(self, provider, postal_code, street_number, suffix):
        self.provider = provider
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix

    def fetch_data(self):
        try:
            url = f"https://api.{self.provider}.nl/webservices/appsinput/?apikey=5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca&method=postcodecheck&postcode={self.postal_code}&street=&huisnummer={self.street_number}&toevoeging={self.suffix if self.suffix else ''}&app_name=afvalwijzer&platform=web&afvaldata={datetime.now().strftime('%Y-%m-%d')}&langs=nl&"
            raw_response = requests.get(url, timeout=60, verify=False)
            raw_response.raise_for_status()
            return raw_response.json()
        except requests.exceptions.RequestException as err:
            raise ValueError(err) from err

    def parse_data(self, data):
        try:
            ophaaldagen_data = data.get("ophaaldagen", {}).get("data", [])
            ophaaldagen_next_data = data.get("ophaaldagenNext", {}).get("data", [])[:10]

            if not ophaaldagen_data and not ophaaldagen_next_data:
                _LOGGER.error("Address not found or no data available!")
                raise KeyError

            collections = []
            for entry in ophaaldagen_data + ophaaldagen_next_data:
                try:
                    collection_date = datetime.strptime(entry["date"], "%Y-%m-%d")
                    waste_type = entry["type"]
                    collections.append(WasteCollection(collection_date, waste_type))
                except (KeyError, ValueError) as parse_err:
                    _LOGGER.warning(f"Skipping invalid entry: {entry} - {parse_err}")

            return collections
        except KeyError as err:
            raise KeyError("Invalid and/or no data received") from err

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    collector = AfvalwijzerCollector("mijnafvalwijzer", "5685AB", 57, "")
    repository = WasteCollectionRepository()

    try:
        data = collector.fetch_data()
        collections = collector.parse_data(data)

        for collection in collections:
            repository.add(collection)

            # print(collection.date)

        _LOGGER.info(f"Loaded waste collections: {repository.get_sorted()}")
    except Exception as e:
        _LOGGER.error(f"Error: {e}")
