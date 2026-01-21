"""Pytest configuration for Afvalwijzer tests."""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

try:
    import requests

    _REQUESTS_AVAILABLE = True
except Exception:
    requests = None
    _REQUESTS_AVAILABLE = False

# Set environment variable to skip runtime setup during tests
os.environ["AFVALWIJZER_SKIP_INIT"] = "1"

# Add custom_components to path for imports
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance for simple tests."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture(autouse=True)
def _block_network_requests(monkeypatch):
    """Prevent real HTTP requests during tests.

    This patches `requests.sessions.Session.request` (used internally by
    `requests.get`/`post`/etc.) to raise an error. Tests should mock the
    provider functions (or requests calls) explicitly if network access is
    required for the test.
    """
    if _REQUESTS_AVAILABLE:

        def _raise(*args, **kwargs):
            raise RuntimeError("Network access disabled during tests")

        monkeypatch.setattr(requests.sessions.Session, "request", _raise)
