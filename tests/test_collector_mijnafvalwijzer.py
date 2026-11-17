"""Tests for the MijnAfvalWijzer collector."""

import pytest
import requests

from custom_components.afvalwijzer.collector import mijnafvalwijzer


def _item(waste_type, date, name_type=None):
    item = {"type": waste_type, "date": date}
    if name_type is not None:
        item["nameType"] = name_type
    return item


def _response(items, next_items=None):
    return {
        "ophaaldagen": {"response": "OK", "data": items, "error": False},
        "ophaaldagenNext": {
            "response": "OK" if next_items else "NOK",
            "data": next_items or [],
        },
    }


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
    """Session returning one response and remembering the URLs."""

    def __init__(self, response):
        """Store the response."""
        self.response = response
        self.urls = []

    def get(self, url, **_kwargs):
        """Answer a GET."""
        self.urls.append(url)
        return self.response


# --- URL ----------------------------------------------------------------------------


def test_build_url_formats_the_address():
    """The postal code is written without a space, in capitals."""
    url = mijnafvalwijzer._build_url("mijnafvalwijzer", "2382 xb", "14", "B")

    assert "postcode=2382XB" in url
    assert "huisnummer=14" in url
    assert "toevoeging=B" in url


def test_build_url_rejects_an_unknown_provider():
    """Only the MijnAfvalWijzer provider is accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        mijnafvalwijzer._build_url("rova", "2382XB", "14", "")


# --- waste data ---------------------------------------------------------------------


def test_waste_types_are_mapped_and_dates_kept():
    """Items as the API returns them: nameType is the provider's own name."""
    response = _response(
        [
            _item("gft", "2026-11-17", "gft+e"),
            _item("pmd", "2026-11-18", "pbd"),
            _item("papier", "2026-11-24", "papier"),
            _item("restafval", "2026-11-25", "restafval"),
        ]
    )

    assert mijnafvalwijzer._parse_waste_data_raw(response) == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "pmd", "date": "2026-11-18"},
        {"type": "papier", "date": "2026-11-24"},
        {"type": "restafval", "date": "2026-11-25"},
    ]


@pytest.mark.parametrize(
    ("name_type", "expected"),
    [("PMD", "pmd"), ("pbd", "pmd"), ("Plastic", "plastic"), (None, "plastic")],
)
def test_generic_plastic_becomes_pmd_when_the_name_says_so(name_type, expected):
    """Many municipalities report PMD as "plastic"; the readable name tells which."""
    response = _response([_item("plastic", "2026-11-18", name_type)])

    assert mijnafvalwijzer._parse_waste_data_raw(response) == [
        {"type": expected, "date": "2026-11-18"}
    ]


def test_next_period_is_added_and_limited_to_25_items():
    """OphaaldagenNext continues the schedule, but only its first 25 items."""
    current = [_item("gft", "2026-11-17")]
    following = [_item("papier", f"2027-01-{day:02d}") for day in range(1, 31)]

    result = mijnafvalwijzer._parse_waste_data_raw(_response(current, following))

    assert len(result) == 1 + 25
    assert result[0] == {"type": "gft", "date": "2026-11-17"}
    assert result[-1] == {"type": "papier", "date": "2027-01-25"}


def test_items_without_a_date_or_type_are_skipped():
    """Incomplete items are dropped, the rest is kept."""
    response = _response(
        [
            _item("gft", ""),
            {"type": "gft"},
            {"date": "2026-11-17"},
            _item("", "2026-11-17"),
            _item("papier", "2026-11-24"),
        ]
    )

    assert mijnafvalwijzer._parse_waste_data_raw(response) == [
        {"type": "papier", "date": "2026-11-24"}
    ]


def test_unknown_waste_types_are_kept_lowercase():
    """A type we don't know yet stays visible."""
    response = _response([_item("Reinigencontainers", "2026-11-17", "bladafval")])

    assert mijnafvalwijzer._parse_waste_data_raw(response) == [
        {"type": "reinigencontainers", "date": "2026-11-17"}
    ]


@pytest.mark.parametrize(
    "response",
    [{}, _response([]), {"ophaaldagen": {"data": []}, "ophaaldagenNext": {}}],
)
def test_no_data_at_all_is_a_key_error(response):
    """An address without a schedule is reported, not returned as empty."""
    with pytest.raises(KeyError):
        mijnafvalwijzer._parse_waste_data_raw(response)


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_get_waste_data_raw_asks_for_data_from_today():
    """The URL limits the response to today onwards."""
    session = FakeSession(FakeResponse(_response([_item("gft", "2026-11-17")])))

    result = mijnafvalwijzer.get_waste_data_raw(
        "mijnafvalwijzer", "2382 XB", "14", "", session=session
    )

    assert result == [{"type": "gft", "date": "2026-11-17"}]
    assert session.urls[0].endswith("&afvaldata=2026-11-17")
    assert "postcode=2382XB" in session.urls[0]


def test_get_waste_data_raw_wraps_request_errors():
    """HTTP errors are raised as ValueError for the coordinator."""
    session = FakeSession(FakeResponse({}, status_code=503))

    with pytest.raises(ValueError):
        mijnafvalwijzer.get_waste_data_raw(
            "mijnafvalwijzer", "2382XB", "14", "", session=session
        )


def test_get_waste_data_raw_without_a_schedule_raises_key_error():
    """No schedule in the answer: the previous schedule is kept by the coordinator."""
    session = FakeSession(FakeResponse(_response([])))

    with pytest.raises(KeyError):
        mijnafvalwijzer.get_waste_data_raw(
            "mijnafvalwijzer", "2382XB", "14", "", session=session
        )


# --- notifications ------------------------------------------------------------------


def _notices(*items):
    return {"data": {"mededelingen": {"data": list(items)}}}


def _notice(**fields):
    return {
        "id": 7,
        "title": "Storing",
        "text": "<p>De <b>GFT</b>-inzameling is verplaatst.</p>",
        "start_date": "2026-11-15",
        **fields,
    }


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_notification_is_cleaned_and_keeps_its_fields():
    """HTML is stripped, entities decoded and whitespace collapsed."""
    notice = _notice(
        text="<p>Zet  het afval\n buiten &amp; <a href='x'>lees meer</a>.</p>",
        position="top",
        description="Omschrijving",
        date="2026-11-14",
        expiration_date="2026-11-30",
    )

    assert mijnafvalwijzer._parse_notification_data_raw(_notices(notice)) == [
        {
            "id": 7,
            "title": "Storing",
            "content": "Zet het afval buiten & lees meer.",
            "position": "top",
            "description": "Omschrijving",
            "date": "2026-11-14",
            "start_date": "2026-11-15",
            "expiration_date": "2026-11-30",
        }
    ]


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_missing_optional_notification_fields_are_empty_strings():
    """Only the id, title, text and start date are normally present."""
    [result] = mijnafvalwijzer._parse_notification_data_raw(_notices(_notice()))

    assert result["description"] == ""
    assert result["date"] == ""
    assert result["expiration_date"] == ""
    assert result["position"] is None


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_notifications_older_than_30_days_are_skipped():
    """Only recent notices are shown; 30 days back is still included."""
    notices = _notices(
        _notice(id=1, start_date="2026-10-18"),  # exactly 30 days ago
        _notice(id=2, start_date="2026-10-17"),  # 31 days ago
    )

    result = mijnafvalwijzer._parse_notification_data_raw(notices)

    assert [n["id"] for n in result] == [1]


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_notification_without_a_usable_start_date_is_kept(caplog):
    """No start date, the empty date 0000-00-00, or a broken one: still shown."""
    notices = _notices(
        _notice(id=1, start_date=""),
        _notice(id=2, start_date="0000-00-00"),
        _notice(id=3, start_date="17-11-2026"),
    )

    result = mijnafvalwijzer._parse_notification_data_raw(notices)

    assert [n["id"] for n in result] == [1, 2, 3]
    assert "Invalid start_date format: 17-11-2026" in caplog.text


@pytest.mark.freeze_time("2026-11-17 09:00:00")
@pytest.mark.parametrize("text", [None, "", "<p></p>", "<br/> &nbsp; "])
def test_notification_without_text_is_skipped(text):
    """A notice that says nothing is not shown."""
    notices = _notices(_notice(text=text))

    assert mijnafvalwijzer._parse_notification_data_raw(notices) == []


@pytest.mark.parametrize("response", [{}, {"data": {}}, _notices()])
def test_no_notifications_gives_an_empty_list(response):
    """An answer without notices is normal."""
    assert mijnafvalwijzer._parse_notification_data_raw(response) == []


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_get_notification_data_raw_fetches_and_parses():
    """The notices come from the same answer as the schedule."""
    session = FakeSession(FakeResponse(_notices(_notice())))

    result = mijnafvalwijzer.get_notification_data_raw(
        "mijnafvalwijzer", "2382XB", "14", "", session=session
    )

    assert [n["id"] for n in result] == [7]
    assert "afvaldata" not in session.urls[0]


def test_get_notification_data_raw_ignores_request_errors(caplog):
    """Notices are optional: a failing request gives none, and a warning."""
    session = FakeSession(FakeResponse({}, status_code=503))

    result = mijnafvalwijzer.get_notification_data_raw(
        "mijnafvalwijzer", "2382XB", "14", "", session=session
    )

    assert result == []
    assert "notification request error" in caplog.text


def test_get_notification_data_raw_ignores_invalid_data(caplog):
    """An answer of the wrong shape gives no notices, and a warning."""
    session = FakeSession(FakeResponse({"data": {"mededelingen": {"data": 5}}}))

    result = mijnafvalwijzer.get_notification_data_raw(
        "mijnafvalwijzer", "2382XB", "14", "", session=session
    )

    assert result == []
    assert "Invalid notification data" in caplog.text
