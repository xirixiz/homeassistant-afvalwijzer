"""Tests that the RD4 collector also fetches next year's calendar."""

from datetime import datetime

import requests

from custom_components.afvalwijzer.collector import rd4

YEAR = datetime.now().year


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
        """Store the payload and status code."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session answering GET requests by URL fragment."""

    def __init__(self, routes):
        """Store the routes as (fragment, response) pairs."""
        self.routes = routes
        self.urls = []

    def get(self, url, **_kwargs):
        """Return the first route whose fragment is in the URL."""
        self.urls.append(url)
        for fragment, response in self.routes:
            if fragment in url:
                return response
        raise AssertionError(f"unexpected URL {url}")


def test_rd4_combines_this_and_next_year():
    """RD4 returns the entries of both years."""
    session = FakeSession(
        [
            (
                f"year={YEAR}",
                FakeResponse(
                    {
                        "success": True,
                        "data": {"items": [[{"date": f"{YEAR}-12-30", "type": "gft"}]]},
                    }
                ),
            ),
            (
                f"year={YEAR + 1}",
                FakeResponse(
                    {
                        "success": True,
                        "data": {
                            "items": [[{"date": f"{YEAR + 1}-01-06", "type": "gft"}]]
                        },
                    }
                ),
            ),
        ]
    )

    result = rd4.get_waste_data_raw("rd4", "1234AB", "1", "", session=session)

    assert [item["date"] for item in result] == [f"{YEAR}-12-30", f"{YEAR + 1}-01-06"]


def test_rd4_ignores_unavailable_next_year():
    """A failing next-year request does not cost the current year."""
    session = FakeSession(
        [
            (
                f"year={YEAR}",
                FakeResponse(
                    {
                        "success": True,
                        "data": {"items": [[{"date": f"{YEAR}-12-30", "type": "gft"}]]},
                    }
                ),
            ),
            (f"year={YEAR + 1}", FakeResponse({}, status_code=404)),
        ]
    )

    result = rd4.get_waste_data_raw("rd4", "1234AB", "1", "", session=session)

    assert [item["date"] for item in result] == [f"{YEAR}-12-30"]
