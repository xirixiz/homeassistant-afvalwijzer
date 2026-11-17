"""Tests for searching the collector by municipality in the config flow."""

from unittest.mock import AsyncMock

import pytest

from custom_components.afvalwijzer.config_flow import (
    ALL_COLLECTORS,
    COLLECTOR_CHOICES,
    AfvalwijzerConfigFlow,
    _resolve_collector,
)
from custom_components.afvalwijzer.const.const import CONF_COLLECTOR
from custom_components.afvalwijzer.const.municipalities import MUNICIPALITY_COLLECTORS


def test_every_municipality_points_to_a_selectable_collector():
    """The generated table only refers to collectors the integration supports."""
    assert set(MUNICIPALITY_COLLECTORS.values()) <= set(ALL_COLLECTORS)


def test_table_is_not_empty_and_has_known_municipalities():
    """Sanity check of the generated data."""
    assert len(MUNICIPALITY_COLLECTORS) > 300
    assert MUNICIPALITY_COLLECTORS["Harderwijk"] == "omrin"
    assert MUNICIPALITY_COLLECTORS["Utrecht"] == "utrecht"


def test_municipalities_are_listed_with_their_collector():
    """A municipality is shown together with the collector that serves it."""
    assert COLLECTOR_CHOICES["Harderwijk (Omrin)"] == "omrin"
    assert COLLECTOR_CHOICES["Omrin"] == "omrin"


def test_municipality_named_like_its_collector_is_listed_once():
    """Amsterdam is both a municipality and a collector: only the collector shows."""
    assert "Amsterdam" in COLLECTOR_CHOICES
    assert not any(text.startswith("Amsterdam (") for text in COLLECTOR_CHOICES)


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("Omrin", "omrin"),
        ("omrin", "omrin"),
        ("  OMRIN ", "omrin"),
        ("Harderwijk (Omrin)", "omrin"),
        ("harderwijk (omrin)", "omrin"),
        ("Súdwest-Fryslân", "sudwestfryslan"),
        ("Nergens", None),
        ("Harderwijk", None),
        ("", None),
    ],
)
def test_resolve_collector(choice, expected):
    """Listed entries (and collector keys) resolve; anything else doesn't."""
    assert _resolve_collector(choice) == expected


async def test_user_step_continues_with_the_collector_of_the_municipality():
    """Choosing a municipality continues the flow with that municipality's collector."""
    flow = AfvalwijzerConfigFlow()
    flow.async_step_address = AsyncMock(return_value={"type": "form"})

    await flow.async_step_user({CONF_COLLECTOR: "Harderwijk (Omrin)"})

    assert flow._collector == "omrin"
    flow.async_step_address.assert_awaited_once()


async def test_user_step_still_accepts_a_collector_key():
    """A collector key keeps working (existing flows and YAML imports)."""
    flow = AfvalwijzerConfigFlow()
    flow.async_step_address = AsyncMock(return_value={"type": "form"})

    await flow.async_step_user({CONF_COLLECTOR: "mijnafvalwijzer"})

    assert flow._collector == "mijnafvalwijzer"


async def test_user_step_rejects_text_that_is_not_a_listed_entry():
    """Free text is rejected with invalid_collector and the flow stays on the step."""
    flow = AfvalwijzerConfigFlow()
    flow.async_step_address = AsyncMock()
    flow.async_show_form = lambda **kwargs: kwargs

    result = await flow.async_step_user({CONF_COLLECTOR: "Nergens"})

    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_COLLECTOR: "invalid_collector"}
    flow.async_step_address.assert_not_awaited()


async def test_user_step_rejects_an_empty_choice():
    """Submitting the blank entry shows invalid_collector instead of picking a collector."""
    flow = AfvalwijzerConfigFlow()
    flow.async_step_address = AsyncMock()
    flow.async_show_form = lambda **kwargs: kwargs

    result = await flow.async_step_user({CONF_COLLECTOR: ""})

    assert result["errors"] == {CONF_COLLECTOR: "invalid_collector"}
    flow.async_step_address.assert_not_awaited()
