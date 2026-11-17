"""Every request the integration makes has a timeout.

A request without one can wait forever, and a refresh that never ends keeps the
entities from ever updating again. The source is checked for every call, the defaults
are checked for being finite, and a run through every collector checks the requests
that are really made.
"""

import ast
import contextlib
import importlib
import inspect
import json
from pathlib import Path
import re

import pytest
import requests

from custom_components.afvalwijzer.collector import ximmio

from .fakes import FakeResponse
from .test_request_error_logging import COLLECTORS

ROOT = Path(__file__).parent.parent / "custom_components" / "afvalwijzer"
SOURCES = sorted(path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts)
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "request"}
SESSION = re.compile(r"^(self\.)?_?session$|^requests$")


def _requests_in(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in HTTP_METHODS
            and SESSION.match(ast.unparse(node.func.value))
        ):
            yield node


def _timeout_of(call):
    for keyword in call.keywords:
        if keyword.arg == "timeout":
            return keyword.value
    return None


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_request_in_the_source_has_a_timeout(path):
    """Each session call passes a timeout, and not None."""
    problems = []
    for call in _requests_in(ast.parse(path.read_text())):
        timeout = _timeout_of(call)
        forwards = any(keyword.arg is None for keyword in call.keywords)
        if forwards:
            continue  # checked below, where the keywords are forwarded from
        if timeout is None:
            problems.append(f"line {call.lineno}: no timeout")
        elif isinstance(timeout, ast.Constant) and timeout.value is None:
            problems.append(f"line {call.lineno}: timeout=None")

    assert not problems, f"{path.name}: {problems}"


def test_the_ximmio_helper_forwards_the_timeout_of_its_callers():
    """The IPv4/IPv6 retry passes **kwargs on, so every caller must give a timeout."""
    tree = ast.parse(Path(ximmio.__file__).read_text())
    callers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "_post_ipv4_then_ipv6"
    ]

    assert len(callers) == 2
    assert all(_timeout_of(call) is not None for call in callers)


def _public_functions():
    for module_name, _provider, _extra in COLLECTORS:
        module = importlib.import_module(
            f"custom_components.afvalwijzer.collector.{module_name}"
        )
        for name in ("get_waste_data_raw", "get_notification_data_raw"):
            function = getattr(module, name, None)
            if function is not None:
                yield pytest.param(function, id=f"{module_name}.{name}")


@pytest.mark.parametrize("function", _public_functions())
def test_the_default_timeout_is_finite(function):
    """The default is a (connect, read) pair of positive numbers, not too long."""
    default = inspect.signature(function).parameters["timeout"].default

    assert isinstance(default, tuple)
    assert len(default) == 2
    connect, read = default
    assert 0 < connect <= 30
    assert 0 < read <= 120


class _RecordingSession:
    """Session that answers everything the same way and records each request."""

    def __init__(self, payload):
        self.payload = payload
        self.requests = []
        self.cookies = requests.cookies.RequestsCookieJar()
        self.headers = {}

    def _answer(self, *_args, **kwargs):
        self.requests.append(kwargs)
        return FakeResponse(
            self.payload,
            text=json.dumps(self.payload) if self.payload is not None else "",
            url="https://x/",
            cookies={"CB_SESSION": "x__AT=t&___TS=1"},
        )

    get = post = put = request = _answer


PAYLOADS = [
    {},
    [],
    {"success": True, "data": {"items": [[{"date": "2099-01-05", "type": "gft"}]]}},
    {"dataList": [{"UniqueId": "u", "Community": "c"}], "items": [{"id": "1"}]},
    [{"bagId": "b", "addressId": "a", "id": 1}],
    {"customData": {"addresses": [{"authenticationUrl": "/x", "address": "A 1,"}]}},
]


@pytest.mark.parametrize("payload", PAYLOADS, ids=lambda p: type(p).__name__)
@pytest.mark.parametrize(("module", "provider", "extra"), COLLECTORS)
def test_every_request_that_is_made_has_a_timeout(module, provider, extra, payload):
    """Whatever the answer, each request the collector makes carries a timeout."""
    collector = importlib.import_module(
        f"custom_components.afvalwijzer.collector.{module}"
    )
    session = _RecordingSession(payload)

    # the answer is made up; what matters is how the requests were made
    with contextlib.suppress(ValueError, KeyError, TypeError, AttributeError):
        collector.get_waste_data_raw(
            provider, "1234AB", "5", "", session=session, **extra
        )

    assert session.requests, "no request made"
    assert all(request.get("timeout") for request in session.requests)
