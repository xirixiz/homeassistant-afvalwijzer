"""Tests for the Reinis collector (Scoop resident website, JSON calendar)."""

import json

import pytest
import requests

from custom_components.afvalwijzer.collector import reinis

BASE = "https://reinis.nl"
ACTION_ID = "40e9e910c92ad2df3a6e7323c73dc0a3658eb0fb12"
NEW_ACTION_ID = "4000000000000000000000000000000000000000ff"
ADDRESS_ID = "8e75bc43-2774-4789-b474-833d96032877"

POSTCODE_HTML = (
    '<script src="/_next/static/chunks/0common.js?dpl=x" async></script>'
    '<script src="/_next/static/chunks/1page.js?dpl=x" async></script>'
)


def _chunk(action_id):
    """Shaped like the minified Next.js chunk that defines the server action."""
    return (
        'let u=(0,n.createServerReference)("'
        + action_id
        + '",r.callServer,void 0,r.findSourceMapURL,"ensureAnonSessionAction");'
    )


CALENDAR = {
    "ok": True,
    "data": {
        "days": [
            {
                "date": "2026-11-13",
                "pickups": [{"date": "2026-11-13", "streamId": "gft", "route": ""}],
            },
            {
                "date": "2026-11-20",
                "pickups": [
                    {"date": "2026-11-20", "streamId": "pmd"},
                    {"date": "2026-11-20", "streamId": "opk"},
                ],
            },
        ]
    },
}


def _action_answer(payload):
    """Return the action's answer in React Server Components format."""
    return '0:{"a":"$@1"}\n1:' + json.dumps(payload) + "\n"


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, text="", status_code=200, payload=None):
        """Store the body, status code and an optional JSON payload."""
        self.text = text
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self):
        """Mirror requests.Response.ok."""
        return self.status_code < 400

    def json(self):
        """Return the payload, or fail like requests for a non-JSON body."""
        if self._payload is None:
            raise requests.exceptions.JSONDecodeError("Expecting value", self.text, 0)
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses, with the URL like requests does."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Error for url: {BASE}/secret?addressId={ADDRESS_ID}",
                response=self,
            )


class FakeSession:
    """Session answering the postcode page, scripts, address action and calendar."""

    def __init__(self, *, action_id=ACTION_ID, post=None, calendar=None):
        """Store the answers; post and calendar may be lists answered in order."""
        self.action_id = action_id
        self.post_answers = post if post is not None else [self._ok_answer()]
        self.calendar_answers = (
            calendar if calendar is not None else [FakeResponse(payload=CALENDAR)]
        )
        self.calls = []
        self.posts = []
        self.calendar_params = []

    @staticmethod
    def _ok_answer():
        return FakeResponse(
            _action_answer({"ok": True, "data": {"addressId": ADDRESS_ID}})
        )

    @staticmethod
    def _next(answers):
        return answers.pop(0) if len(answers) > 1 else answers[0]

    def get(self, url, params=None, **_kwargs):
        """Answer a page, a script or the calendar."""
        path = url.removeprefix(BASE)
        self.calls.append(f"GET {path.split('?')[0]}")
        if path.startswith("/postcode"):
            return FakeResponse(POSTCODE_HTML)
        if path.startswith("/_next/static/chunks/0common.js"):
            return FakeResponse("console.log(1)")
        if path.startswith("/_next/static/chunks/1page.js"):
            return FakeResponse(_chunk(self.action_id))
        if path.startswith("/api/proxy/pickups/calendar"):
            self.calendar_params.append(params)
            return self._next(self.calendar_answers)
        raise AssertionError(f"unexpected URL {url}")

    def post(self, url, data=None, headers=None, **_kwargs):
        """Answer the address action."""
        self.calls.append(f"POST {url.removeprefix(BASE).split('?')[0]}")
        self.posts.append((json.loads(data), headers))
        return self._next(self.post_answers)

    def count(self, call):
        """Return how many requests were exactly this call."""
        return self.calls.count(call)


@pytest.fixture(autouse=True)
def _clear_cache():
    reinis._ACTION_ID_CACHE.clear()
    yield
    reinis._ACTION_ID_CACHE.clear()


def _run(session, postal_code="3232 pw", house_number="19", suffix=""):
    return reinis.get_waste_data_raw(
        "reinis", postal_code, house_number, suffix, session=session
    )


@pytest.mark.freeze_time("2026-11-12 12:00:00")
def test_reinis_reads_the_json_calendar():
    """The address is set through the action, then the calendar is read as JSON."""
    session = FakeSession()

    result = _run(session)

    assert result == [
        {"date": "2026-11-13", "type": "gft"},
        {"date": "2026-11-20", "type": "pmd"},
        {"date": "2026-11-20", "type": "papier"},
    ]
    body, headers = session.posts[0]
    assert body == [{"postcode": "3232PW", "huisnummer": "19", "toev": "$undefined"}]
    assert headers["Next-Action"] == ACTION_ID
    assert session.calendar_params == [
        {"addressId": ADDRESS_ID, "from": "2026-11-12", "to": "2027-11-12"}
    ]


def test_reinis_scans_the_scripts_from_the_end():
    """The page-specific script comes last, so it is found first."""
    session = FakeSession()

    _run(session)

    assert session.calls == [
        "GET /postcode",
        "GET /_next/static/chunks/1page.js",
        "POST /postcode",
        "GET /api/proxy/pickups/calendar",
    ]


def test_reinis_sends_the_suffix():
    """A house number suffix is passed as toevoeging."""
    session = FakeSession()

    _run(session, suffix="a")

    assert session.posts[0][0][0]["toev"] == "a"


def test_reinis_reuses_the_action_id():
    """A second refresh is two requests: the address action and the calendar."""
    _run(FakeSession())
    session = FakeSession()

    assert len(_run(session)) == 3
    assert session.calls == ["POST /postcode", "GET /api/proxy/pickups/calendar"]


@pytest.mark.parametrize("status", [400, 404, 405])
def test_reinis_looks_up_a_stale_action_id_again(status):
    """A new build of the website: the cached id is rejected and found again."""
    reinis._ACTION_ID_CACHE[BASE] = "stale"
    session = FakeSession(
        action_id=NEW_ACTION_ID,
        post=[
            FakeResponse("Server action not found.", status),
            FakeSession._ok_answer(),
        ],
    )

    assert len(_run(session)) == 3
    assert session.calls == [
        "POST /postcode",  # rejected
        "GET /postcode",
        "GET /_next/static/chunks/1page.js",
        "POST /postcode",
        "GET /api/proxy/pickups/calendar",
    ]
    assert session.posts[0][1]["Next-Action"] == "stale"
    assert session.posts[1][1]["Next-Action"] == NEW_ACTION_ID
    assert reinis._ACTION_ID_CACHE[BASE] == NEW_ACTION_ID


def test_reinis_unparseable_action_answer_counts_as_stale():
    """A 200 without the action's result also means the id no longer works."""
    reinis._ACTION_ID_CACHE[BASE] = "stale"
    session = FakeSession(
        post=[FakeResponse("<html>not found</html>"), FakeSession._ok_answer()]
    )

    assert len(_run(session)) == 3
    assert reinis._ACTION_ID_CACHE[BASE] == ACTION_ID


def test_reinis_server_error_keeps_the_cached_action_id():
    """A 5xx is an outage, not a new build."""
    reinis._ACTION_ID_CACHE[BASE] = ACTION_ID
    session = FakeSession(post=[FakeResponse("", 503)])

    with pytest.raises(ValueError):
        _run(session)

    assert reinis._ACTION_ID_CACHE[BASE] == ACTION_ID
    assert session.calls == ["POST /postcode"]


def test_reinis_unknown_address_returns_nothing(caplog):
    """Reinis's own reason is logged and no calendar is requested."""
    answer = FakeResponse(_action_answer({"ok": False, "error": "ADDRESS_NOT_FOUND"}))
    session = FakeSession(post=[answer])

    assert _run(session, house_number="99999") == []

    assert "ADDRESS_NOT_FOUND" in caplog.text
    assert "GET /api/proxy/pickups/calendar" not in session.calls
    assert reinis._ACTION_ID_CACHE[BASE] == ACTION_ID  # the id itself worked


def test_reinis_missing_action_id_raises():
    """A website change that hides the action id is reported, not swallowed."""
    session = FakeSession()
    session.action_id = "nothing here"

    with pytest.raises(ValueError):
        _run(session)
    assert reinis._ACTION_ID_CACHE == {}


@pytest.mark.parametrize(
    "calendar",
    [
        FakeResponse(payload={"ok": False, "error": {"code": "FEED_UNAVAILABLE"}}),
        FakeResponse(payload=["not", "a", "dict"]),
        FakeResponse(payload={"ok": True, "data": {"days": "nope"}}),
        FakeResponse(payload={"ok": True}),
        FakeResponse("<html>blocked</html>"),
    ],
)
def test_reinis_invalid_calendar_raises(calendar):
    """A calendar that isn't what we expect fails the refresh (schedule is kept)."""
    with pytest.raises(ValueError):
        _run(FakeSession(calendar=[calendar]))


def test_reinis_skips_incomplete_pickups():
    """Pickups without a date or stream are skipped, the rest is kept."""
    days = [
        {
            "date": "2026-11-13",
            "pickups": [
                {"date": "2026-11-13", "streamId": "gft"},
                {"date": "2026-11-13"},
                {"streamId": "pmd"},
                {"date": "2026-11-13", "streamId": "  "},
                None,
            ],
        },
        None,
    ]
    session = FakeSession(
        calendar=[FakeResponse(payload={"ok": True, "data": {"days": days}})]
    )

    assert _run(session) == [{"date": "2026-11-13", "type": "gft"}]


def test_reinis_calendar_without_pickups_returns_nothing(caplog):
    """An address without kerbside pickups gives no data and a warning."""
    empty = FakeResponse(payload={"ok": True, "data": {"days": []}})

    assert _run(FakeSession(calendar=[empty])) == []
    assert "no kerbside pickups" in caplog.text


@pytest.mark.parametrize(
    ("stream", "expected"),
    [
        ("rest", "restafval"),
        ("glas", "glas"),
        ("textiel", "textiel"),
        ("groente", "gft"),
    ],
)
def test_reinis_other_streams_map_to_the_usual_types(stream, expected):
    """The other streams the site offers map to the standard waste types."""
    days = [
        {"date": "2026-11-13", "pickups": [{"date": "2026-11-13", "streamId": stream}]}
    ]
    session = FakeSession(
        calendar=[FakeResponse(payload={"ok": True, "data": {"days": days}})]
    )

    assert _run(session) == [{"date": "2026-11-13", "type": expected}]


def test_reinis_errors_do_not_log_the_url_or_address_id(caplog):
    """The request URL holds the address id, so only the error type is logged."""
    session = FakeSession(calendar=[FakeResponse("", 500)])

    with pytest.raises(ValueError) as err:
        _run(session)

    assert "HTTPError 500" in caplog.text
    for text in (caplog.text, str(err.value)):
        assert ADDRESS_ID not in text
        assert "secret" not in text
        assert "reinis.nl" not in text
