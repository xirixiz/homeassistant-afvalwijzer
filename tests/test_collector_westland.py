"""Tests for the Westland Ximmio host."""

from custom_components.afvalwijzer.collector import ximmio
from custom_components.afvalwijzer.const.const import SENSOR_COLLECTORS_XIMMIO


def test_westland_uses_the_wasteprod2_host():
    """Westland is served from wasteprod2api, like the other Ximmio-v2 providers."""
    assert ximmio._build_url("westland") == "https://wasteprod2api.ximmio.com"


def test_every_wasteprod2_provider_has_a_host():
    """The host table lists westland alongside the other wasteprod2 providers."""
    assert "westland" in SENSOR_COLLECTORS_XIMMIO
