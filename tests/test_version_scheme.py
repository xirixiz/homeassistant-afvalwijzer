"""Tests for the release version scheme.

scripts/verify-version cannot import AwesomeVersion (the release workflow blocks
egress to PyPI), so it orders versions using the version grammar instead. These
tests are where that shortcut is justified: they assert every version the scheme
can produce is valid AwesomeVersion, is correctly flagged as a pre-release, and
orders the same way under both comparators.
"""

from awesomeversion import AwesomeVersion
import pytest

from update_version import compute_next_version, sort_key

# Ascending order, mixing betas and stables across sequences and years.
_ASCENDING = [
    "2025.1042",
    "2026.1000",
    "2026.1018",
    "2026.1019.0b1",
    "2026.1019.0b2",
    "2026.1019.0b10",
    "2026.1019",
    "2026.1020.0b1",
    "2026.1020",
]


@pytest.mark.parametrize("version", _ASCENDING)
def test_scheme_versions_are_valid_awesomeversion(version):
    """Every version in the scheme parses as CalVer, not UNKNOWN."""
    parsed = AwesomeVersion(version)
    assert parsed.valid, f"{version} is not a valid AwesomeVersion"


@pytest.mark.parametrize("version", _ASCENDING)
def test_beta_flag_matches_the_grammar(version):
    """AwesomeVersion agrees with the grammar about which versions are betas."""
    assert AwesomeVersion(version).beta is ("0b" in version)


def test_sort_key_orders_the_same_way_as_awesomeversion():
    """The dependency-free comparator agrees with AwesomeVersion pairwise."""
    for lower, higher in zip(_ASCENDING, _ASCENDING[1:], strict=False):
        assert sort_key(lower) < sort_key(higher), f"{lower} !< {higher} (sort_key)"
        assert AwesomeVersion(lower) < AwesomeVersion(higher), (
            f"{lower} !< {higher} (AwesomeVersion)"
        )


def test_beta_sorts_below_its_own_stable():
    """The rule that makes re-opening a shipped sequence impossible."""
    assert sort_key("2026.1018.0b3") < sort_key("2026.1018")
    assert AwesomeVersion("2026.1018.0b3") < AwesomeVersion("2026.1018")


def test_retired_beta_suffix_is_rejected():
    """The old '-bNN' style is why this scheme exists: AwesomeVersion can't use it."""
    assert not AwesomeVersion("2026.1018-b01").valid
    with pytest.raises(ValueError, match="not a recognised version"):
        sort_key("2026.1018-b01")


@pytest.mark.parametrize(
    ("current", "beta", "expected"),
    [
        ("2026.1018", False, "2026.1019"),
        ("2026.1018", True, "2026.1019.0b1"),
        ("2026.1019.0b1", True, "2026.1019.0b2"),
        ("2026.1019.0b2", False, "2026.1019"),
    ],
)
def test_computed_versions_move_forward(current, beta, expected):
    """Each step update_version.py can take is an increase, never a downgrade."""
    assert compute_next_version(current, beta=beta) == expected
    assert sort_key(current) < sort_key(expected)
