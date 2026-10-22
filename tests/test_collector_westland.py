"""Tests for the Westland Ximmio host."""

from custom_components.afvalwijzer.collector import ximmio


def test_westland_uses_the_wasteprod2_host():
    """Westland is served from wasteprod2api, like the other Ximmio-v2 providers."""
    assert ximmio._build_url("westland") == "https://wasteprod2api.ximmio.com"
