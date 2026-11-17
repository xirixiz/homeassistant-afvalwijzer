"""Tests for the MijnAfvalHulp collector: the login, the iCal link and the errors."""

import pytest

from custom_components.afvalwijzer.collector import mijnafvalhulp

from .fakes import FakeResponse, FakeSession

BASE = "https://mijn.afvalhulp.nl"
ICAL_URL = f"{BASE}/api/v1/ical/0123abcd-4567-89ef-0123-456789abcdef/calendar.ics"
FORM = '<html><meta name="csrf-token" content="tok-1"></html>'
SCHEDULE = f'<a href="{ICAL_URL}">calendar</a>'
ICAL = (
    "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Groene container\r\n"
    "DTSTART;VALUE=DATE:20261113\r\nEND:VEVENT\r\nEND:VCALENDAR"
)


def _session(*, ical=ICAL, form=FORM, schedule=SCHEDULE):
    return FakeSession(
        FakeResponse(text=form),
        FakeResponse(text="", url=f"{BASE}/postcode/done"),
        FakeResponse(text=schedule),
        FakeResponse(text=ical),
    )


def _run(session, suffix=""):
    return mijnafvalhulp.get_waste_data_raw(
        "mijnafvalhulp", "1234 ab", "5", suffix, session=session, timeout=(1, 1)
    )


# --- small helpers -----------------------------------------------------------------


def test_build_url_refuses_an_unknown_provider():
    """Only the listed provider has an address."""
    assert mijnafvalhulp._build_url("mijnafvalhulp") == BASE
    with pytest.raises(ValueError, match="Invalid provider"):
        mijnafvalhulp._build_url("nonexistent")


@pytest.mark.parametrize(
    ("html", "token"),
    [
        ('<meta name="csrf-token" content="meta-token">', "meta-token"),
        ('<input type="hidden" name="_token" value="input-token">', "input-token"),
        (
            '<input name="_token" value="input"><meta name="csrf-token" content="meta">',
            "meta",
        ),
        ("<html>nothing here</html>", None),
        ("", None),
    ],
)
def test_csrf_token_is_found_in_the_meta_tag_or_the_form(html, token):
    """The meta tag wins; the hidden form field is the fallback."""
    assert mijnafvalhulp._get_csrf_token(html) == token


def test_ical_url_is_found_in_the_schedule_page():
    """The calendar link has a fixed shape with a uuid."""
    assert mijnafvalhulp._get_ical_url(f"x {ICAL_URL} y") == ICAL_URL


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<html>login</html>",
        f"{BASE}/api/v1/ical/not-a-uuid/calendar.ics",
        "https://other.example/api/v1/ical/0123abcd-4567-89ef-0123-456789abcdef/calendar.ics",
    ],
)
def test_ical_url_missing_means_the_login_failed(html):
    """Without the link the error says the login may have failed."""
    with pytest.raises(ValueError, match="login may have failed"):
        mijnafvalhulp._get_ical_url(html)


# --- the flow ----------------------------------------------------------------------


def test_flow_logs_in_and_reads_the_calendar():
    """Form page, login, schedule page and calendar, in that order."""
    session = _session()

    assert _run(session, suffix="b") == [{"type": "gft", "date": "2026-11-13"}]
    assert session.urls() == [
        f"{BASE}/postcode",
        f"{BASE}/postcode",
        f"{BASE}/pickup-schedule",
        ICAL_URL,
    ]
    login = session.calls[1][2]
    assert login["data"] == {
        "_token": "tok-1",
        "postcode": "1234AB",
        "housenumber": "5",
        "addition": "b",
    }
    assert login["allow_redirects"] is True
    # the schedule page is asked with the page the login ended on as referer
    assert session.calls[2][2]["headers"]["Referer"] == f"{BASE}/postcode/done"


def test_flow_without_a_suffix_sends_an_empty_addition():
    """No suffix is an empty string, not None."""
    session = _session()

    _run(session, suffix=None)

    assert session.calls[1][2]["data"]["addition"] == ""


def test_flow_without_a_csrf_token_is_a_value_error():
    """A login page without a token can't be submitted."""
    session = _session(form="<html>maintenance</html>")

    with pytest.raises(ValueError, match="CSRF token"):
        _run(session)
    assert len(session.calls) == 1


def test_flow_without_an_ical_link_is_a_value_error():
    """A schedule page without the link means the login failed."""
    session = _session(schedule="<html>please log in</html>")

    with pytest.raises(ValueError, match="login may have failed"):
        _run(session)


def test_flow_with_an_empty_calendar_gives_no_pickups(caplog):
    """An empty calendar is logged and returns an empty list."""
    assert _run(_session(ical="")) == []
    assert "No waste data found for mijnafvalhulp" in caplog.text


def test_flow_with_an_unreadable_calendar_is_a_value_error(monkeypatch):
    """A calendar the parser rejects is reported as invalid data."""

    def _broken(*_args, **_kwargs):
        raise KeyError("DTSTART")

    monkeypatch.setattr(mijnafvalhulp, "parse_ical_waste_data", _broken)

    with pytest.raises(ValueError, match="invalid or no data received"):
        _run(_session())


@pytest.mark.parametrize("failing_request", [0, 1, 2, 3])
def test_flow_turns_an_http_error_into_a_value_error(failing_request):
    """Whichever request fails, the error is a ValueError without the address."""
    responses = [
        FakeResponse(text=FORM),
        FakeResponse(text="", url=f"{BASE}/postcode/done"),
        FakeResponse(text=SCHEDULE),
        FakeResponse(text=ICAL),
    ]
    responses[failing_request] = FakeResponse(status_code=503)
    session = FakeSession(*responses)

    with pytest.raises(ValueError, match=r"request failed \(HTTPError 503\)") as raised:
        _run(session)
    assert "1234" not in str(raised.value)
