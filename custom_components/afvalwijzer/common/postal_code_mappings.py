"""Postal-code-specific waste type overrides.

This module allows certain waste type labels to be remapped differently
depending on the 4-digit postal code area. Overrides defined here take
priority over the global ``WASTE_TYPE_MAPPING`` in ``main_functions.py``.

Each entry in ``POSTAL_CODE_OVERRIDES`` is a tuple of:
  * A ``range`` or ``frozenset`` of 4-digit postal code prefixes (inclusive start, exclusive end for range).
  * A ``dict`` mapping raw waste type labels (lowercase) to standardized keys.

Example::

    (range(7940, 7945), {
        "keukenafval": "vet-goed",
    })

This matches postal codes 7940XX through 7944XX and renames
``keukenafval`` to ``vet-goed``.
"""

from __future__ import annotations

POSTAL_CODE_OVERRIDES: list[tuple[range | frozenset[int], dict[str, str]]] = [
    (
        range(7940, 7945),  # Meppel
        {
            "keukenafval": "vet-goed",
        },
    ),
    (
        # Goirle / Riel area. Note: 5043 is deliberately *not* included here.
        # It was originally part of this frozenset (see #622), but that
        # postal code prefix turned out to be Tilburg-proper - a check
        # against the official BAG/PDOK address register found postal code
        # 5043 has no addresses registered in the Goirle municipality at
        # all (every full postal code under that prefix is Tilburg), where
        # "rest-gft"/"rest-gfte" is a real, wanted collection type. Applying
        # the override there silently dropped it for Tilburg residents
        # sharing that prefix (#664).
        frozenset({5050, 5051, 5052, 5133}),
        {
            "rest-gft": "ignore",
            "rest-gfte": "ignore",
        },
    ),
    # Add more overrides here as needed, for example:
    # (range(1000, 1100), {
    #     "restafval": "huisvuil",
    #     "some_type": "other_type",
    # }),
]


def get_postal_code_override(postal_digits: int, item_name: str) -> str | None:
    """Look up a postal-code-specific waste type override.

    Args:
        postal_digits: The 4-digit numeric prefix of the postal code (e.g. 7941).
        item_name: The cleaned (lowercase, stripped) waste type label.

    Returns:
        The overridden waste type key if a match is found, otherwise ``None``.

    """
    for code_range, mapping in POSTAL_CODE_OVERRIDES:
        if postal_digits in code_range:
            override = mapping.get(item_name)
            if override is not None:
                return override
    return None
