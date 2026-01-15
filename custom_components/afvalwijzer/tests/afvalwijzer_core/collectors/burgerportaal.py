from collections.abc import Callable
from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const import BURGERPORTAAL_API_KEY, COLLECTORS_BURGERPORTAAL
from ..model import WasteCollection
from .base import BaseCollector

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class BurgerportaalCollector(BaseCollector):
    def __init__(
        self,
        *,
        provider: str,
        postal_code: str,
        street_number: str,
        suffix: str,
        waste_type_rename: Callable[[str], str | None],
    ):
        if provider not in COLLECTORS_BURGERPORTAAL:
            raise ValueError(f"Invalid provider: {provider}")

        self.provider = provider
        self.organisation_id = COLLECTORS_BURGERPORTAAL[provider]
        self.postal_code = postal_code.strip().replace(" ", "").upper()
        self.street_number = str(street_number).strip()
        self.suffix = (suffix or "").strip().upper()
        self.waste_type_rename = waste_type_rename

        self._id_token: str | None = None

    def fetch_raw(self) -> dict[str, Any]:
        self._authenticate()
        address_id = self._fetch_address_id()
        calendar = self._fetch_calendar(address_id)
        return {"calendar": calendar}

    def parse(self, raw: dict[str, Any]) -> list[WasteCollection]:
        out: list[WasteCollection] = []

        for item in raw.get("calendar", []) or []:
            collection_date = item.get("collectionDate")
            fraction = item.get("fraction")

            if not collection_date or not fraction:
                continue

            waste_type = self.waste_type_rename(fraction.strip().lower())
            if not waste_type:
                continue

            day_str = collection_date.split("T", 1)[0]
            pickup_day = datetime.strptime(day_str, "%Y-%m-%d").date()

            out.append(WasteCollection.from_any(pickup_day, waste_type))

        return sorted(out, key=lambda x: (x.day, x.waste_type.lower()))

    def _authenticate(self) -> None:
        r = requests.post(
            f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={BURGERPORTAAL_API_KEY}"
        )
        r.raise_for_status()
        data = r.json()

        refresh_token = data.get("refreshToken")
        if not refresh_token:
            raise ValueError("Failed to obtain refresh token")

        r = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={BURGERPORTAAL_API_KEY}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        r.raise_for_status()
        data = r.json()

        self._id_token = data.get("id_token")
        if not self._id_token:
            raise ValueError("Failed to obtain id token")

    def _fetch_address_id(self) -> str:
        if not self._id_token:
            raise ValueError("Not authenticated")

        r = requests.get(
            f"https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{self.organisation_id}/address",
            params={
                "zipcode": self.postal_code,
                "housenumber": self.street_number,
            },
            headers={"authorization": self._id_token},
            verify=False,
        )
        r.raise_for_status()
        addresses = r.json()

        if not addresses:
            raise KeyError("Address not found")

        if self.suffix:
            for item in addresses:
                addition = item.get("addition")
                if addition and addition.casefold() == self.suffix.casefold():
                    address_id = item.get("addressId")
                    if address_id:
                        return address_id

        address_id = addresses[0].get("addressId")
        if not address_id:
            raise KeyError("addressId missing from address response")
        return address_id

    def _fetch_calendar(self, address_id: str) -> list[dict[str, Any]]:
        if not self._id_token:
            raise ValueError("Not authenticated")

        r = requests.get(
            f"https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{self.organisation_id}/address/{address_id}/calendar",
            headers={"authorization": self._id_token},
            verify=False,
        )
        r.raise_for_status()
        return r.json()
