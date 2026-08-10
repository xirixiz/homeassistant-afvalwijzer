"""Tests for MainCollector.provider_supports_notifications in main_collector.py."""

from custom_components.afvalwijzer.collector.main_collector import MainCollector


def test_opzet_provider_supports_notifications():
    """A provider from the opzet collector set supports notifications."""
    assert MainCollector.provider_supports_notifications("alphenaandenrijn") is True


def test_mijnafvalwijzer_provider_supports_notifications():
    """The mijnafvalwijzer provider supports notifications."""
    assert MainCollector.provider_supports_notifications("mijnafvalwijzer") is True


def test_unrelated_provider_does_not_support_notifications():
    """A provider outside the known notification-capable sets returns False."""
    assert MainCollector.provider_supports_notifications("rova") is False


def test_unknown_provider_does_not_support_notifications():
    """An unrecognized provider name returns False rather than raising."""
    assert MainCollector.provider_supports_notifications("not_a_real_provider") is False


def test_provider_supports_notifications_is_case_and_whitespace_insensitive():
    """Matching is normalized the same way MainCollector normalizes provider."""
    assert MainCollector.provider_supports_notifications(" MijnAfvalwijzer ") is True


def test_provider_supports_notifications_handles_none():
    """A missing provider (e.g. unset config) does not raise."""
    assert MainCollector.provider_supports_notifications(None) is False
