"""Property-based tests: what must hold for any input, not just the ones we thought of.

Hypothesis generates the inputs. The runs are derandomized, so a failure in CI is the
same failure on a developer's machine.
"""

import contextlib
from datetime import date, datetime, timedelta
import importlib
import json
import string
from unittest.mock import patch

from hypothesis import HealthCheck, given, settings, strategies as st
import pytest
import requests

from custom_components.afvalwijzer.common.main_functions import (
    describe_request_error,
    format_postal_code,
    parse_ical_waste_data,
    waste_type_rename,
)
from custom_components.afvalwijzer.common.sensor_utils import (
    normalize_waste_type_key,
    parse_and_apply_value,
)
from custom_components.afvalwijzer.common.waste_data_transformer import (
    WasteDataTransformer,
)

from .fakes import FakeResponse
from .test_request_error_logging import COLLECTORS

FAST = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)
TEXT = st.text(max_size=60)
POSTAL_CODES = st.one_of(
    st.from_regex(r"[1-9][0-9]{3} ?[A-Za-z]{2}", fullmatch=True), TEXT
)


# --- text helpers -------------------------------------------------------------------


@FAST
@given(label=TEXT, postal_code=st.one_of(st.none(), POSTAL_CODES))
def test_renaming_never_fails_and_is_stable(label, postal_code):
    """Any label gives a text, and renaming the result changes nothing."""
    renamed = waste_type_rename(label, postal_code)

    assert isinstance(renamed, str)
    assert waste_type_rename(renamed, postal_code) == renamed


@FAST
@given(label=st.text(alphabet=string.printable, max_size=40))
def test_renaming_ignores_case_and_surrounding_spaces(label):
    """The lookup is the same for any spelling of the same label."""
    assert waste_type_rename(f"  {label.upper()}\t") == waste_type_rename(label.lower())


@FAST
@given(postal_code=POSTAL_CODES)
def test_formatting_a_postal_code_never_fails(postal_code):
    """Any text gives a text; a well-formed code gives digits and capital letters."""
    formatted = format_postal_code(postal_code)

    assert isinstance(formatted, str)
    if len(postal_code.replace(" ", "")) == 6 and postal_code[:4].isdigit():
        compact = postal_code.replace(" ", "")
        if compact[4:].isalpha() and compact.isascii():
            assert formatted == compact.upper()


@FAST
@given(key=TEXT)
def test_normalized_keys_are_lower_case_with_underscores(key):
    """Translation keys have no capitals and no hyphens."""
    normalized = normalize_waste_type_key(key)

    assert normalized == normalized.lower()
    assert "-" not in normalized


@FAST
@given(
    message=st.text(min_size=8, alphabet=st.characters(categories=["L", "N"])),
    status=st.one_of(st.none(), st.integers(100, 599)),
)
def test_describing_an_error_never_quotes_its_message(message, status):
    """Only the type and the status come out, whatever the message holds."""
    response = type("Response", (), {"status_code": status})() if status else None
    error = requests.exceptions.HTTPError(message, response=response)

    described = describe_request_error(error)

    assert described.startswith("HTTPError")
    assert message not in described.replace("HTTPError", "")
    assert (str(status) in described) is bool(status)


# --- parsers ------------------------------------------------------------------------

ICAL_LINE = st.one_of(
    st.just("BEGIN:VEVENT"),
    st.just("END:VEVENT"),
    st.builds("SUMMARY:{}".format, TEXT),
    st.builds(
        "DTSTART;VALUE=DATE:{}".format, st.text(alphabet="0123456789", max_size=10)
    ),
    TEXT,
)


@FAST
@given(lines=st.lists(ICAL_LINE, max_size=30))
def test_ical_parsing_gives_complete_events_for_any_text(lines):
    """Whatever the text, every pickup has a date and a type."""
    result = parse_ical_waste_data("\r\n".join(lines))

    for pickup in result:
        assert pickup["type"]
        datetime.strptime(pickup["date"], "%Y-%m-%d")


JSON = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(-(2**31), 2**31),
        st.floats(allow_nan=False),
        st.text(max_size=30),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(
            st.sampled_from(
                [
                    "data",
                    "items",
                    "date",
                    "type",
                    "success",
                    "valid",
                    "dataList",
                    "customData",
                    "calendar",
                    "addresses",
                    "collections",
                    "pickups",
                    "bagId",
                    "id",
                    "name",
                    "fraction",
                    "ok",
                    "days",
                    "dates",
                    "code",
                    "collectionDate",
                    "timestamp",
                    "streamId",
                    "afvalwijzerFractieCode",
                    "menu_title",
                    "ophaaldatum",
                    "_pickupTypeText",
                    "pickupDates",
                    "garbage",
                    "response",
                    "formatted",
                    "nl",
                    "calendar_data",
                ]
            ),
            children,
            max_size=4,
        ),
    ),
    max_leaves=12,
)


class _Session:
    """Session answering every request with the same JSON."""

    def __init__(self, payload):
        self.response = FakeResponse(
            payload,
            text=json.dumps(payload),
            url="https://x/",
            cookies={"CB_SESSION": "x__AT=t&___TS=1"},
        )
        self.cookies = requests.cookies.RequestsCookieJar()
        self.headers = {}

    def _answer(self, *_args, **_kwargs):
        return self.response

    get = post = put = request = _answer


# What the main collector turns into "invalid data" for the user.
HANDLED = (ValueError, KeyError, TypeError, AttributeError)


@pytest.mark.parametrize(("module", "provider", "extra"), COLLECTORS)
@FAST
@given(payload=JSON)
def test_no_collector_fails_in_an_unexpected_way_on_any_answer(
    module, provider, extra, payload
):
    """A collector either returns pickups or raises an error that is reported."""
    collector = importlib.import_module(
        f"custom_components.afvalwijzer.collector.{module}"
    )

    with contextlib.suppress(*HANDLED):
        result = collector.get_waste_data_raw(
            provider, "1234AB", "5", "", session=_Session(payload), **extra
        )
        assert isinstance(result, list)
        for pickup in result:
            assert set(pickup) == {"type", "date"}
            datetime.strptime(pickup["date"], "%Y-%m-%d")


# --- values and the transformer -----------------------------------------------------


@FAST
@given(value=st.one_of(TEXT, st.integers(), st.none(), st.floats(allow_nan=False)))
def test_parsing_a_sensor_value_never_fails(value):
    """Anything is parsed or kept as it is, with no device class."""
    parsed, device_class = parse_and_apply_value(value)

    assert device_class is None
    assert parsed is not None or value is None


TODAY = date(2026, 11, 13)
PICKUP = st.builds(
    lambda kind, offset: {
        "type": kind,
        "date": (TODAY + timedelta(days=offset)).isoformat(),
    },
    st.sampled_from(["gft", "pmd", "papier", "restafval", "textiel", "ignore"]),
    st.integers(-40, 400),
)


def _transform(pickups, exclude_today, exclude_list):
    now = datetime(2026, 11, 13, 9, 0)
    with (
        patch(
            "custom_components.afvalwijzer.common.waste_data_transformer.dt_util.now",
            return_value=now,
        ),
        patch(
            "custom_components.afvalwijzer.common.next_sensor_data.dt_util.now",
            return_value=now,
        ),
        patch(
            "custom_components.afvalwijzer.common.day_sensor_data.dt_util.now",
            return_value=now,
        ),
    ):
        return WasteDataTransformer(pickups, exclude_today, exclude_list, "geen")


@FAST
@given(
    pickups=st.lists(PICKUP, max_size=40),
    exclude_today=st.sampled_from(["true", "false", "yes", "no"]),
    exclude=st.lists(
        st.sampled_from(["gft", "pmd", "papier", "restafval"]), max_size=3
    ),
)
def test_the_transformer_keeps_its_promises_for_any_schedule(
    pickups, exclude_today, exclude
):
    """Excluded and ignored types are gone, dates lie ahead, the lists are tidy."""
    sensor = _transform(pickups, exclude_today, ",".join(exclude))

    provider = sensor.waste_data_provider
    assert not set(provider) & set(exclude)
    assert "ignore" not in provider
    assert sensor.waste_types_provider == sorted(set(sensor.waste_types_provider))
    first_day = TODAY if exclude_today in ("false", "no") else TODAY + timedelta(days=1)
    for value in provider.values():
        assert value == "geen" or value.date() >= first_day

    custom = sensor.waste_data_custom
    assert set(custom) >= {"next_date", "next_in_days", "next_type", "today"}
    if custom["next_in_days"] != "geen":
        assert custom["next_in_days"] >= 1
        assert custom["next_date"].date() > TODAY
    else:
        assert custom["next_type"] == "geen"
