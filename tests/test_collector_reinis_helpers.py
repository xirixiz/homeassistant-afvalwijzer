"""Tests for the small Reinis helpers: provider lookup, action id and answers."""

import pytest

from custom_components.afvalwijzer.collector import reinis

from .fakes import FakeResponse, FakeSession

ID_ONE = "a" * 40
ID_TWO = "b" * 40


def _chunk(action_id):
    return f'("{action_id}",r.callServer,"ensureAnonSessionAction")'


def _page(*names):
    return "".join(
        f'<script src="/_next/static/chunks/{n}.js"></script>' for n in names
    )


def _lookup(session):
    return reinis._find_action_id(session, "https://x", timeout=(1, 1), verify=True)


def test_build_base_url_refuses_an_unknown_provider():
    """Only listed providers have an address."""
    assert reinis._build_base_url("reinis").startswith("https://")
    with pytest.raises(ValueError, match="Invalid provider"):
        reinis._build_base_url("nonexistent")


def test_the_action_id_is_found_in_the_last_chunk_that_has_it():
    """Page chunks come last, so they are searched first."""
    session = FakeSession(
        FakeResponse(text=_page("common", "page")),
        FakeResponse(text=_chunk(ID_TWO)),
        FakeResponse(text=_chunk(ID_ONE)),
    )

    assert _lookup(session) == ID_TWO
    assert session.urls()[1].endswith("/_next/static/chunks/page.js")


def test_a_chunk_that_cannot_be_loaded_is_skipped():
    """A failing chunk doesn't stop the search in the others."""
    session = FakeSession(
        FakeResponse(text=_page("common", "page")),
        FakeResponse(status_code=500),
        FakeResponse(text=_chunk(ID_ONE)),
    )

    assert _lookup(session) == ID_ONE


def test_without_the_action_the_website_changed():
    """No chunk has the action: the error says what is missing."""
    session = FakeSession(
        FakeResponse(text=_page("common")), FakeResponse(text="nothing here")
    )

    with pytest.raises(ValueError, match="could not find the address action"):
        _lookup(session)


def test_the_first_action_result_is_returned():
    """Lines of the React Server Components answer that are not results are skipped."""
    text = "\n".join(
        [
            "0:[something]",
            "no colon here",
            '1:{"unrelated": true}',
            "2:{broken json",
            '3:{"ok": true, "id": "x"}',
            '4:{"ok": false}',
        ]
    )

    assert reinis._action_result(text) == {"ok": True, "id": "x"}


@pytest.mark.parametrize("text", ["", "0:[1]\n1:null", '1:{"nothing": 1}'])
def test_an_answer_without_a_result_gives_none(text):
    """Nothing that looks like the action's result."""
    assert reinis._action_result(text) is None
