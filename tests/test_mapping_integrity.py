"""The waste type mapping is a table people edit by hand; these tests keep it sound."""

import ast
from collections import Counter
import json
from pathlib import Path

import pytest

from custom_components.afvalwijzer.common.main_functions import (
    WASTE_TYPE_MAPPING,
    waste_type_rename,
)
from custom_components.afvalwijzer.common.postal_code_mappings import (
    POSTAL_CODE_OVERRIDES,
    get_postal_code_override,
)
from custom_components.afvalwijzer.common.sensor_utils import (
    WASTE_TYPE_COLORS,
    WASTE_TYPE_ICONS,
    normalize_waste_type_key,
)

COMPONENT = Path(__file__).parent.parent / "custom_components" / "afvalwijzer"
TARGETS = set(WASTE_TYPE_MAPPING.values())
# Not a pickup: the transformer drops it, so it needs no icon, color or name.
IGNORE = "ignore"


# --- the table itself ---------------------------------------------------------------


def test_keys_are_trimmed_lower_case_and_not_empty():
    """The lookup lower-cases and trims its input, so a key that isn't can't match."""
    bad = [k for k in WASTE_TYPE_MAPPING if not k or k != k.strip().lower()]

    assert not bad, f"keys that can never match: {bad}"


def test_targets_are_lower_case_without_spaces():
    """Targets become translation keys and parts of entity ids."""
    bad = [t for t in TARGETS if not t or t != t.lower() or " " in t]

    assert not bad, f"targets that are not standard keys: {bad}"


def test_no_key_is_written_twice():
    """A repeated key in the dict literal silently overrides the first one."""
    tree = ast.parse((COMPONENT / "common" / "main_functions.py").read_text())
    keys = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and getattr(node.target, "id", "") == "WASTE_TYPE_MAPPING"
        ):
            keys = [key.value for key in node.value.keys]
    assert keys, "WASTE_TYPE_MAPPING not found in the source"

    repeated = [key for key, count in Counter(keys).items() if count > 1]
    assert not repeated, f"keys written more than once: {repeated}"


@pytest.mark.parametrize("target", sorted(TARGETS))
def test_mapping_a_target_again_changes_nothing(target):
    """Standard keys are stable: renaming a target gives the target."""
    assert waste_type_rename(target) == target


def test_unknown_labels_are_kept_as_they_are():
    """What isn't mapped is passed on, cleaned, not dropped or guessed."""
    assert waste_type_rename("  Iets Nieuws ") == "iets nieuws"


# --- postal code overrides ----------------------------------------------------------


@pytest.mark.parametrize(
    ("prefixes", "labels"),
    POSTAL_CODE_OVERRIDES,
    ids=[str(sorted(prefixes)[:1]) for prefixes, _ in POSTAL_CODE_OVERRIDES],
)
def test_an_override_is_well_formed(prefixes, labels):
    """Four-digit areas, normalized labels and results that exist."""
    assert all(1000 <= prefix <= 9999 for prefix in prefixes)
    assert labels
    for label, target in labels.items():
        assert label == label.strip().lower(), f"{label!r} can never match"
        assert target == IGNORE or target in TARGETS | {"vet-goed"}, (
            f"{label!r} -> {target!r} is not a standard type"
        )


def test_overrides_for_the_same_label_do_not_overlap():
    """Where two overrides cover one area and label, the first silently wins."""
    seen: dict[tuple[int, str], str] = {}
    clashes = []
    for prefixes, labels in POSTAL_CODE_OVERRIDES:
        for prefix in prefixes:
            for label, target in labels.items():
                if (prefix, label) in seen and seen[(prefix, label)] != target:
                    clashes.append((prefix, label))
                seen[(prefix, label)] = target

    assert not clashes, f"conflicting overrides: {clashes}"


@pytest.mark.parametrize(
    ("prefixes", "labels"), POSTAL_CODE_OVERRIDES, ids=lambda v: None
)
def test_an_override_applies_in_its_whole_area_and_only_there(prefixes, labels):
    """Every code of the area is overridden; the code next to it is not."""
    label, target = next(iter(labels.items()))
    first, last = min(prefixes), max(prefixes)

    for prefix in prefixes:
        assert get_postal_code_override(prefix, label) == target
    outside = next(code for code in (first - 1, last + 1, 1000) if code not in prefixes)
    assert get_postal_code_override(outside, label) != target


# --- every type needs an icon, a color and a name -----------------------------------
#
# These are the gaps that exist today. The tests compare the exact set, so a new type
# without an icon, color or translation fails, and so does fixing one without
# removing it from the list.

KNOWN_WITHOUT_ICON = {"kca-locatie", "papier-pmd", "rest-gft", "zachte-plastics"}
KNOWN_WITHOUT_COLOR = {
    "best-tas",
    "grip",
    "kca-locatie",
    "papier-pmd",
    "pmd-restafval",
    "rest-gft",
    "restafvalzakken",
    "restwagen",
    "sorti",
    "zachte-plastics",
}
KNOWN_WITHOUT_NAME = {
    "kca",
    "kca-locatie",
    "luiers",
    "papier-pmd",
    "pmd-restafval",
    "rest-gft",
    "sorti",
    "textiel",
    "zachte-plastics",
}


def _sensor_translations(language):
    path = COMPONENT / "translations" / f"{language}.json"
    return set(json.loads(path.read_text())["entity"]["sensor"])


def test_types_without_an_icon_are_the_known_ones():
    """A new standard type gets an icon."""
    missing = {t for t in TARGETS if t != IGNORE and t not in WASTE_TYPE_ICONS}

    assert missing == KNOWN_WITHOUT_ICON


def test_types_without_a_color_are_the_known_ones():
    """A new standard type gets a calendar color."""
    missing = {t for t in TARGETS if t != IGNORE and t not in WASTE_TYPE_COLORS}

    assert missing == KNOWN_WITHOUT_COLOR


@pytest.mark.parametrize("language", ["en", "nl"])
def test_types_without_a_name_are_the_known_ones(language):
    """A new standard type gets a name in every language."""
    names = _sensor_translations(language)
    missing = {
        t for t in TARGETS if t != IGNORE and normalize_waste_type_key(t) not in names
    }

    assert missing == KNOWN_WITHOUT_NAME


def test_icons_and_colors_are_listed_under_normalized_keys():
    """The lookups use the target as it is, so lower case with hyphens."""
    for table in (WASTE_TYPE_ICONS, WASTE_TYPE_COLORS):
        assert all(key == key.strip().lower() for key in table)


def test_both_languages_name_the_same_types():
    """Dutch and English have the same sensors."""
    assert _sensor_translations("en") == _sensor_translations("nl")
