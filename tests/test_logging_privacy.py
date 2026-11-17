"""No log line or raised error in the integration may hold the address.

The runtime tests in test_request_error_logging.py cover the requests that fail. This
test reads the source, so it covers every branch, including the ones only a real
provider reaches: it checks each log call and each error raised from a handler of a
request error. A request error's message holds the full URL, which holds the address.
"""

import ast
import logging
from pathlib import Path

import pytest
import requests

from custom_components.afvalwijzer.collector import opzet, rd4

from .fakes import FakeResponse, FakeSession

ROOT = Path(__file__).parent.parent / "custom_components" / "afvalwijzer"
SOURCES = sorted(path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts)

# Names that hold (a part of) the address or a URL with it.
ADDRESS_NAMES = {
    "url",
    "next_url",
    "base_url_with_address",
    "postal_code",
    "corrected_postal_code",
    "house_number",
    "street_name",
    "address",
    "zipcode",
}
# Calls that describe an error without its message.
SAFE_WRAPPERS = {"describe_request_error", "type"}


def _calls_to_logger(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "_LOGGER"
        ):
            yield node


def _names(nodes):
    for node in nodes:
        yield from (n for n in ast.walk(node) if isinstance(n, ast.Name))


def _attributes(nodes):
    for node in nodes:
        yield from (n for n in ast.walk(node) if isinstance(n, ast.Attribute))


def _handles_request_errors(handler: ast.ExceptHandler) -> bool:
    """Return True when the handler names a requests error among what it catches."""
    if handler.type is None:
        return False
    caught = {n.attr for n in ast.walk(handler.type) if isinstance(n, ast.Attribute)}
    caught |= {n.id for n in ast.walk(handler.type) if isinstance(n, ast.Name)}
    return "RequestException" in caught


def _unsafe_uses(handler: ast.ExceptHandler):
    """Yield where the caught error itself ends up in a log call or a raised error."""
    bound = handler.name
    if not bound:
        return

    def _walk(node, safe):
        if isinstance(node, ast.Name) and node.id == bound and not safe:
            yield node
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            safe = safe or name in SAFE_WRAPPERS
        for child in ast.iter_child_nodes(node):
            yield from _walk(child, safe)

    for node in ast.walk(handler):
        if node is handler:
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "_LOGGER"
        ):
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                yield from _walk(arg, False)
        elif isinstance(node, ast.Raise) and node.exc is not None:
            # `raise X(...) from err` is fine: only the message of X counts.
            yield from _walk(node.exc, False)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_log_calls_do_not_name_the_address(path):
    """No log call passes the postal code, house number, street or a URL."""
    tree = ast.parse(path.read_text())
    problems = []
    for call in _calls_to_logger(tree):
        values = [*call.args[1:], *(k.value for k in call.keywords)]
        names = {n.id for n in _names(values)} & ADDRESS_NAMES
        attributes = {n.attr for n in _attributes(values)} & {"url"}
        if names or attributes:
            problems.append(f"line {call.lineno}: {sorted(names | attributes)}")

    assert not problems, f"{path.name} logs address data: {problems}"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_request_errors_are_only_described_never_quoted(path):
    """A handler of a request error logs and raises its type, not its message."""
    tree = ast.parse(path.read_text())
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _handles_request_errors(node):
            problems += [
                f"line {use.lineno}: {node.name} is logged or raised as it is"
                for use in _unsafe_uses(node)
            ]

    assert not problems, f"{path.name} quotes an error: {problems}"


# --- the three places the test above found ------------------------------------------

POSTAL_CODE = "9876ZX"
HOUSE_NUMBER = "4321"


def _leaky_error():
    return requests.exceptions.ConnectionError(
        f"Max retries exceeded with url: /api?postcode={POSTAL_CODE}&huisnummer={HOUSE_NUMBER}"
    )


def test_rd4_next_year_failing_logs_no_address(caplog):
    """The calendar of next year is optional; its failure is logged without the URL."""
    ok = FakeResponse(
        {"success": True, "data": {"items": [[{"date": "2099-01-05", "type": "gft"}]]}}
    )
    session = FakeSession(ok, _leaky_error())

    with caplog.at_level(logging.DEBUG):
        rd4.get_waste_data_raw("rd4", POSTAL_CODE, HOUSE_NUMBER, "", session=session)

    assert "RD4: no data for" in caplog.text
    assert POSTAL_CODE not in caplog.text
    assert HOUSE_NUMBER not in caplog.text


def test_rd4_non_numeric_house_number_is_not_logged(caplog):
    """The house number isn't repeated in the log when it can't be used."""
    with caplog.at_level(logging.DEBUG):
        result = rd4.get_notification_data_raw(
            "rd4", POSTAL_CODE, "12abc", "", session=FakeSession(FakeResponse({}))
        )

    assert result == []
    assert "not numeric" in caplog.text
    assert "12abc" not in caplog.text


def test_opzet_calendar_failing_logs_no_address(caplog):
    """A calendar that can't be fetched is logged without the URL."""
    session = FakeSession(_leaky_error())

    with caplog.at_level(logging.DEBUG):
        result = opzet._fetch_calendar_raw_temp(
            session, "https://x", "bag-1", 2099, timeout=(1, 1), verify=True
        )

    assert result == []
    assert "calendar for 2099 not available" in caplog.text
    assert POSTAL_CODE not in caplog.text
    assert HOUSE_NUMBER not in caplog.text
