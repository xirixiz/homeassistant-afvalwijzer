"""Tests for searching the collector by municipality in the config flow."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from custom_components.afvalwijzer.config_flow import (
    ALL_COLLECTORS,
    COLLECTOR_SCHEMA,
    AfvalwijzerConfigFlow,
    _collector_options,
    _resolve_collector,
)
from custom_components.afvalwijzer.const.const import COLLECTOR_LABELS, CONF_COLLECTOR
from custom_components.afvalwijzer.const.municipalities import MUNICIPALITY_COLLECTORS


def test_every_municipality_points_to_a_selectable_collector():
    """The generated table only refers to collectors the integration supports."""
    assert set(MUNICIPALITY_COLLECTORS.values()) <= set(ALL_COLLECTORS)


def test_table_is_not_empty_and_has_known_municipalities():
    """Sanity check of the generated data."""
    assert len(MUNICIPALITY_COLLECTORS) > 300
    assert MUNICIPALITY_COLLECTORS["Harderwijk"] == "omrin"
    assert MUNICIPALITY_COLLECTORS["Utrecht"] == "utrecht"


def test_option_values_are_unique():
    """Every dropdown option has its own value."""
    values = [option["value"] for option in _collector_options()]

    assert len(values) == len(set(values))


def test_options_contain_collectors_and_municipalities():
    """Both collectors and municipalities (with their collector) are listed."""
    labels = {option["value"]: option["label"] for option in _collector_options()}

    assert labels["omrin"] == COLLECTOR_LABELS["omrin"]
    assert labels["municipality:Harderwijk"] == "Harderwijk (Omrin)"


def test_municipality_named_like_its_collector_is_listed_once():
    """Amsterdam is both a municipality and a collector: only the collector shows."""
    labels = [option["label"] for option in _collector_options()]

    assert labels.count("Amsterdam") == 1
    assert not any(label.startswith("Amsterdam (") for label in labels)


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        ("omrin", "omrin"),
        ("municipality:Harderwijk", "omrin"),
        ("municipality:'s-Gravenhage", MUNICIPALITY_COLLECTORS["'s-Gravenhage"]),
    ],
)
def test_resolve_collector(choice, expected):
    """A municipality choice resolves to its collector, a collector stays as is."""
    assert _resolve_collector(choice) == expected


def test_schema_accepts_a_municipality_and_rejects_unknown_ones():
    """Only listed municipalities can be chosen."""
    assert COLLECTOR_SCHEMA({CONF_COLLECTOR: "municipality:Harderwijk"}) == {
        CONF_COLLECTOR: "municipality:Harderwijk"
    }
    with pytest.raises(vol.Invalid):
        COLLECTOR_SCHEMA({CONF_COLLECTOR: "municipality:Nergens"})


async def test_user_step_stores_the_collector_of_the_chosen_municipality():
    """Choosing a municipality continues the flow with that municipality's collector."""
    flow = AfvalwijzerConfigFlow()
    flow.async_step_address = AsyncMock(return_value={"type": "form"})

    await flow.async_step_user({CONF_COLLECTOR: "municipality:Harderwijk"})

    assert flow._collector == "omrin"
    flow.async_step_address.assert_awaited_once()


async def test_user_step_still_accepts_a_collector():
    """Choosing a collector directly keeps working."""
    flow = AfvalwijzerConfigFlow()
    flow.async_step_address = AsyncMock(return_value={"type": "form"})

    await flow.async_step_user({CONF_COLLECTOR: "mijnafvalwijzer"})

    assert flow._collector == "mijnafvalwijzer"
