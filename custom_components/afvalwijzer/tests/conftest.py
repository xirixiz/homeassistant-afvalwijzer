"""Pytest configuration for Afvalwijzer tests."""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

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
