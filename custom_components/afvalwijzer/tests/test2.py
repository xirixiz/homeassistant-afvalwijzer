"""
Manual runner that outputs Home Assistant friendly JSON.

Goals
1. First upcoming pickup date per waste type
2. Overview fields for HA
   today
   tomorrow
   day_after_tomorrow
   first_next_date
   first_next_type
   first_next_in_days
3. Easy to add more collectors later

Run examples
python waste_runner.py auto mijnafvalwijzer 1234AB 10 A
python waste_runner.py opzet dar 1234AB 10 A
python waste_runner.py afvalwijzer mijnafvalwijzer 1234AB 10 A
"""

import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_LOGGER = logging.getLogger(__name__)

SENSOR_COLLECTORS_OPZET = {
    "afval3xbeter": "https://afval3xbeter.nl",
    "afvalstoffendienst": "https://afvalstoffendienst.nl",
    "afvalstoffendienstkalender": "https://afvalstoffendienst.nl",
    "alphenaandenrijn": "https://afvalkalender.alphenaandenrijn.nl",
    "berkelland": "https://afvalkalender.gemeenteberkelland.nl",
    "blink": "https://mijnblink.nl",
    "cranendonck": "https://afvalkalender.cranendonck.nl",
    "cyclus": "https://cyclusnv.nl",
    "dar": "https://afvalkalender.dar.nl",
    "defryskemarren": "https://afvalkalender.defryskemarren.nl",
    "denhaag": "https://huisvuilkalender.denhaag.nl",
    "gad": "https://inzamelkalender.gad.nl",
    "geertruidenberg": "https://afval.geertruidenberg.nl",
    "hvc": "https://inzamelkalender.hvcgroep.nl",
    "lingewaard": "https://afvalwijzer.lingewaard.nl",
    "middelburg-vlissingen": "https://afvalwijzer.middelburgvlissingen.nl",
    "mijnafvalzaken": "https://mijnafvalzaken.nl",
    "montfoort": "https://cyclusnv.nl",
    "offalkalinder": "https://www.offalkalinder.nl",
    "peelenmaas": "https://afvalkalender.peelenmaas.nl",
    "prezero": "https://inzamelwijzer.prezero.nl",
    "purmerend": "https://afvalkalender.purmerend.nl",
    "rwm": "https://rwm.nl",
    "saver": "https://saver.nl",
    "schouwen-duiveland": "https://afvalkalender.schouwen-duiveland.nl",
    "sliedrecht": "https://afvalkalender.sliedrecht.nl",
    "spaarnelanden": "https://afvalwijzer.spaarnelanden.nl",
    "sudwestfryslan": "https://afvalkalender.sudwestfryslan.nl",
    "suez": "https://inzamelwijzer.prezero.nl",
    "venray": "https://afvalkalender.venray.nl",
    "voorschoten": "https://afvalkalender.voorschoten.nl",
    "waalre": "https://afvalkalender.waalre.nl",
    "zrd": "https://www.zrd.nl",
}


def waste_type_rename(raw: str) -> Optional[str]:
    """
    Placeholder.
    Replace with your integration logic.
    Should return normalized waste type or None to skip.
    """
    s = (raw or "").strip().lower()
    if not s:
        return None

    mapping = {
        "gft": "gft",
        "pmd": "pmd",
        "papier": "papier",
        "restafval": "restafval",
        "kerstbomen": "kerstbomen",
    }
    return mapping.get(s, s)


@dataclass(frozen=True, slots=True)
class WasteCollection:
    day: date
    waste_type: str

    @staticmethod
    def from_any(day_value: Any, waste_type: str) -> "WasteCollection":
        if isinstance(day_value, datetime):
            d = day_value.date()
        elif isinstance(day_value, date):
            d = day_value
        elif isinstance(day_value, str):
            d = datetime.strptime(day_value, "%Y-%m-%d").date()
        else:
            raise TypeError(f"day_value must be date, datetime, or str, got {type(day_value)}")
        return WasteCollection(day=d, waste_type=waste_type)

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.waste_type, "date": self.day.isoformat()}


class WasteCollectionRepository:
    def __init__(self, items: Optional[Iterable[WasteCollection]] = None):
        self._items: List[WasteCollection] = list(items) if items else []

    def add_many(self, items: Iterable[WasteCollection]) -> None:
        self._items.extend(items)

    def sorted(self) -> List[WasteCollection]:
        return sorted(self._items, key=lambda x: (x.day, x.waste_type.lower()))

    def upcoming(self, from_day: Optional[date] = None) -> List[WasteCollection]:
        from_day = from_day or date.today()
        return [x for x in self.sorted() if x.day >= from_day]

    def on_day(self, d: date) -> List[WasteCollection]:
        return [x for x in self.sorted() if x.day == d]

    def first_upcoming_day(self, from_day: Optional[date] = None) -> Optional[date]:
        up = self.upcoming(from_day)
        return up[0].day if up else None

    def first_upcoming_type(self, from_day: Optional[date] = None) -> Optional[str]:
        first_day = self.first_upcoming_day(from_day)
        if not first_day:
            return None
        items = self.on_day(first_day)
        if not items:
            return None
        return sorted(items, key=lambda x: x.waste_type.lower())[0].waste_type

    def first_upcoming_by_type(self, from_day: Optional[date] = None) -> Dict[str, str]:
        res: Dict[str, str] = {}
        for item in self.upcoming(from_day):
            if item.waste_type not in res:
                res[item.waste_type] = item.day.isoformat()
        return res


class Collector(Protocol):
    def collect(self) -> List[WasteCollection]:
        ...


class BaseCollector:
    def collect(self) -> List[WasteCollection]:
        raw = self.fetch_raw()
        return self.parse(raw)

    def fetch_raw(self) -> Dict[str, Any]:
        raise NotImplementedError

    def parse(self, raw: Dict[str, Any]) -> List[WasteCollection]:
        raise NotImplementedError


class AfvalwijzerCollector(BaseCollector):
    def __init__(self, provider: str, postal_code: str, street_number: str, suffix: str):
        self.provider = provider
        self.postal_code = postal_code.strip().replace(" ", "").upper()
        self.street_number = str(street_number).strip()
        self.suffix = (suffix or "").strip().upper()

    def fetch_raw(self) -> Dict[str, Any]:
        url = (
            f"https://api.{self.provider}.nl/webservices/appsinput/"
            f"?apikey=5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca"
            f"&method=postcodecheck"
            f"&postcode={self.postal_code}"
            f"&street="
            f"&huisnummer={self.street_number}"
            f"&toevoeging={self.suffix}"
            f"&app_name=afvalwijzer"
            f"&platform=web"
            f"&afvaldata={date.today().isoformat()}"
            f"&langs=nl&"
        )
        r = requests.get(url, timeout=60, verify=False)
        r.raise_for_status()
        return r.json()

    def parse(self, raw: Dict[str, Any]) -> List[WasteCollection]:
        part1 = raw.get("ophaaldagen", {}).get("data", []) or []
        part2 = raw.get("ophaaldagenNext", {}).get("data", []) or []
        if not part1 and not part2:
            raise KeyError("No pickup data returned")

        out: List[WasteCollection] = []
        for entry in (part1 + part2):
            try:
                out.append(WasteCollection.from_any(entry["date"], entry["type"]))
            except Exception as e:
                _LOGGER.warning("Skipping invalid entry: %s (%s)", entry, e)
        return out


class OpzetCollector(BaseCollector):
    def __init__(
        self,
        provider: str,
        postal_code: str,
        street_number: str,
        suffix: str,
        base_url_map: Dict[str, str],
    ):
        if provider not in base_url_map:
            raise ValueError(f"Invalid provider: {provider}")

        self.provider = provider
        self.base_url = base_url_map[provider].rstrip("/")
        self.postal_code = postal_code.strip().replace(" ", "").upper()
        self.street_number = str(street_number).strip()
        self.suffix = (suffix or "").strip().upper()

    def fetch_raw(self) -> Dict[str, Any]:
        url_address = f"{self.base_url}/rest/adressen/{self.postal_code}-{self.street_number}"
        r_addr = requests.get(url_address, timeout=60, verify=False)
        r_addr.raise_for_status()
        addresses = r_addr.json()
        if not addresses:
            raise KeyError("No address results returned")

        bag_id = self._select_bag_id(addresses, self.suffix)

        url_waste = f"{self.base_url}/rest/adressen/{bag_id}/afvalstromen"
        r_waste = requests.get(url_waste, timeout=60, verify=False)
        r_waste.raise_for_status()
        streams = r_waste.json()

        return {"bag_id": bag_id, "streams": streams}

    def parse(self, raw: Dict[str, Any]) -> List[WasteCollection]:
        streams = raw.get("streams") or []
        out: List[WasteCollection] = []
        for item in streams:
            pickup = item.get("ophaaldatum")
            if not pickup:
                continue

            menu_title = (item.get("menu_title") or "").strip().lower()
            wt = waste_type_rename(menu_title)
            if not wt:
                continue

            try:
                pickup_day = datetime.strptime(pickup, "%Y-%m-%d").date()
            except ValueError as e:
                _LOGGER.warning("Skipping invalid date: %s (%s)", pickup, e)
                continue

            out.append(WasteCollection.from_any(pickup_day, wt))
        return out

    @staticmethod
    def _select_bag_id(addresses: List[Dict[str, Any]], suffix: str) -> str:
        if len(addresses) > 1 and suffix:
            for item in addresses:
                if item.get("huisletter") == suffix or item.get("huisnummerToevoeging") == suffix:
                    bag = item.get("bagId")
                    if bag:
                        return bag
        bag = addresses[0].get("bagId")
        if not bag:
            raise KeyError("bagId missing from address response")
        return bag


def build_ha_json(repo: WasteCollectionRepository) -> Dict[str, Any]:
    today = date.today()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    day_after = date.fromordinal(today.toordinal() + 2)

    first_day = repo.first_upcoming_day(today)
    first_type = repo.first_upcoming_type(today)

    first_next_date = first_day.isoformat() if first_day else None
    first_next_in_days = (first_day - today).days if first_day else None

    payload = {
        "today": [x.to_dict() for x in repo.on_day(today)],
        "tomorrow": [x.to_dict() for x in repo.on_day(tomorrow)],
        "day_after_tomorrow": [x.to_dict() for x in repo.on_day(day_after)],
        "first_next_date": first_next_date,
        "first_next_type": first_type,
        "first_next_in_days": first_next_in_days,
        "first_upcoming_by_type": repo.first_upcoming_by_type(today),
        "upcoming": [x.to_dict() for x in repo.upcoming(today)],
        "last_update": datetime.now().isoformat(),
    }
    return payload


def make_collector(family: str, provider: str, postal_code: str, street_number: str, suffix: str) -> Collector:
    family = (family or "auto").strip().lower()
    provider = (provider or "").strip().lower()

    if family == "opzet":
        return OpzetCollector(provider, postal_code, street_number, suffix, SENSOR_COLLECTORS_OPZET)

    if family == "afvalwijzer":
        return AfvalwijzerCollector(provider, postal_code, street_number, suffix)

    if family == "auto":
        if provider in SENSOR_COLLECTORS_OPZET:
            return OpzetCollector(provider, postal_code, street_number, suffix, SENSOR_COLLECTORS_OPZET)
        return AfvalwijzerCollector(provider, postal_code, street_number, suffix)

    raise ValueError(f"Unknown collector family: {family}")


def usage() -> None:
    print("Usage: python waste_runner.py <family> <provider> <postal_code> <street_number> [suffix]")
    print("family: auto | afvalwijzer | opzet")


def main(argv: List[str]) -> int:
    logging.basicConfig(level=logging.INFO)

    if len(argv) < 5 or len(argv) > 6:
        usage()
        return 1

    family, provider, postal_code, street_number = argv[1:5]
    suffix = argv[5] if len(argv) == 6 else ""

    try:
        collector = make_collector(family, provider, postal_code, street_number, suffix)
        items = collector.collect()

        repo = WasteCollectionRepository(items)
        out = build_ha_json(repo)

        print(json.dumps(out, ensure_ascii=False))
        return 0

    except Exception as e:
        _LOGGER.error("Error: %s", e)
        print(json.dumps({"error": str(e), "last_update": datetime.now().isoformat()}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
