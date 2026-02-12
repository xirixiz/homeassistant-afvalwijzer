"""Tests for postal-code-specific waste type overrides."""

from unittest.mock import patch

from custom_components.afvalwijzer.common.main_functions import waste_type_rename
from custom_components.afvalwijzer.common.postal_code_mappings import (
    POSTAL_CODE_OVERRIDES,
    get_postal_code_override,
)

# ---------------------------------------------------------------------------
# Tests for get_postal_code_override
# ---------------------------------------------------------------------------


class TestGetPostalCodeOverride:
    """Tests for the low-level override lookup function."""

    def test_match_in_range(self):
        """Postal code digit inside a configured range returns the override."""
        assert get_postal_code_override(7941, "keukenafval") == "vet-goed"

    def test_match_at_range_start(self):
        """Boundary: first digit of the range matches."""
        assert get_postal_code_override(7940, "keukenafval") == "vet-goed"

    def test_match_at_range_end(self):
        """Boundary: last digit of the range (inclusive) matches."""
        assert get_postal_code_override(7944, "keukenafval") == "vet-goed"

    def test_no_match_outside_range(self):
        """Postal code digit outside any range returns None."""
        assert get_postal_code_override(1234, "keukenafval") is None

    def test_no_match_just_above_range(self):
        """Digit one beyond the range end returns None."""
        assert get_postal_code_override(7945, "keukenafval") is None

    def test_no_match_unknown_type(self):
        """Known range but unknown waste type returns None."""
        assert get_postal_code_override(7941, "unknown_waste") is None

    def test_first_matching_range_wins(self):
        """When multiple ranges overlap, the first match wins."""
        test_overrides = [
            (range(1000, 2000), {"papier": "oud-papier"}),
            (range(1500, 2500), {"papier": "karton"}),
        ]
        with patch.object(
            __import__(
                "custom_components.afvalwijzer.common.postal_code_mappings",
                fromlist=["POSTAL_CODE_OVERRIDES"],
            ),
            "POSTAL_CODE_OVERRIDES",
            test_overrides,
        ):
            # 1500 is in both ranges; first entry should win
            assert get_postal_code_override(1500, "papier") == "oud-papier"


# ---------------------------------------------------------------------------
# Tests for waste_type_rename with postal_code
# ---------------------------------------------------------------------------


class TestWasteTypeRenameWithPostalCode:
    """Tests for waste_type_rename when a postal_code is supplied."""

    def test_override_takes_priority(self):
        """Postal-code override wins over global mapping."""
        result = waste_type_rename("keukenafval", "7941AB")
        assert result == "vet-goed"

    def test_global_mapping_when_no_override(self):
        """Global mapping is used when postal code has no override for that type."""
        result = waste_type_rename("gft", "7941AB")
        assert result == "gft"

    def test_global_mapping_for_unrelated_postal_code(self):
        """Outside the override range, normal global mapping applies."""
        result = waste_type_rename("gft", "1234AB")
        assert result == "gft"

    def test_no_postal_code_uses_global(self):
        """When postal_code is None, global mapping is used (backward compat)."""
        result = waste_type_rename("gft", None)
        assert result == "gft"

    def test_empty_postal_code_uses_global(self):
        """When postal_code is empty string, global mapping is used."""
        result = waste_type_rename("gft", "")
        assert result == "gft"

    def test_short_postal_code_uses_global(self):
        """When postal_code is too short, global mapping is used."""
        result = waste_type_rename("keukenafval", "79")
        # Without valid 4-digit prefix, override should not activate
        assert result == "keukenafval"

    def test_default_no_postal_code_arg(self):
        """Calling without postal_code arg still works (backward compat)."""
        result = waste_type_rename("gft")
        assert result == "gft"

    def test_unmapped_type_returned_cleaned(self):
        """Unknown type with postal code returns cleaned input."""
        result = waste_type_rename("  SomeRandomType  ", "7941AB")
        assert result == "somerandomtype"

    def test_case_insensitive_override(self):
        """Override lookup is case-insensitive (input is lowered before check)."""
        result = waste_type_rename("Keukenafval", "7942XY")
        assert result == "vet-goed"

    def test_multiple_overrides_per_range(self):
        """Multiple waste types can be overridden for the same postal code range."""
        test_overrides = [
            (
                range(5000, 5010),
                {
                    "type_a": "override_a",
                    "type_b": "override_b",
                },
            ),
        ]
        with patch(
            "custom_components.afvalwijzer.common.main_functions.get_postal_code_override",
        ) as mock_override:
            # Simulate the override function using test data
            def side_effect(digits, name):
                for r, m in test_overrides:
                    if digits in r and name in m:
                        return m[name]
                return None

            mock_override.side_effect = side_effect

            assert waste_type_rename("type_a", "5005AB") == "override_a"
            assert waste_type_rename("type_b", "5005AB") == "override_b"
            # Unmapped type falls through to global
            assert waste_type_rename("gft", "5005AB") == "gft"


# ---------------------------------------------------------------------------
# Smoke test: POSTAL_CODE_OVERRIDES structure is valid
# ---------------------------------------------------------------------------


class TestPostalCodeOverridesStructure:
    """Verify that POSTAL_CODE_OVERRIDES is well-formed."""

    def test_overrides_is_list(self):
        """POSTAL_CODE_OVERRIDES should be a list."""
        assert isinstance(POSTAL_CODE_OVERRIDES, list)

    def test_each_entry_is_tuple_of_range_and_dict(self):
        """Each entry must be a (range, dict) tuple."""
        for entry in POSTAL_CODE_OVERRIDES:
            assert isinstance(entry, tuple), f"Expected tuple, got {type(entry)}"
            assert len(entry) == 2, f"Expected 2-tuple, got {len(entry)}-tuple"
            code_range, mapping = entry
            assert isinstance(code_range, range), (
                f"Expected range, got {type(code_range)}"
            )
            assert isinstance(mapping, dict), f"Expected dict, got {type(mapping)}"

    def test_mapping_keys_are_lowercase(self):
        """All override keys must be lowercase."""
        for _, mapping in POSTAL_CODE_OVERRIDES:
            for key in mapping:
                assert key == key.lower(), f"Key '{key}' should be lowercase"

    def test_mapping_values_are_strings(self):
        """All override values must be strings."""
        for _, mapping in POSTAL_CODE_OVERRIDES:
            for key, value in mapping.items():
                assert isinstance(value, str), f"Value for '{key}' should be str"
