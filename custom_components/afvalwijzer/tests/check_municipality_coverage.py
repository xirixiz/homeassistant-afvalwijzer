#!/usr/bin/env python3
"""Check municipality coverage of test addresses.

This script compares the municipalities in your test addresses against
all municipalities in the Netherlands to identify gaps in coverage.

Usage:
  python3 scripts/check_municipality_coverage.py
  python3 scripts/check_municipality_coverage.py --show-covered
  python3 scripts/check_municipality_coverage.py --export coverage_report.txt
"""

import argparse
import logging
import pickle
import sys

from .test_data import TEST_ADDRESSES

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger(__name__)


def get_all_municipalities(index_path: str) -> set:
    """Get all municipalities from the postcode index."""

    try:
        with open(index_path, "rb") as f:
            index = pickle.load(f)
        municipalities = {m for m in index.values() if m}
        return municipalities
    except FileNotFoundError:
        LOGGER.error("Error: Index file not found at %s", index_path)
        LOGGER.error("Run: scripts/convert-zst-to-pkl")
        sys.exit(2)
    except Exception as e:
        LOGGER.error("Error loading index: %s", e)
        sys.exit(2)


def get_covered_municipalities(addresses: list, index_path: str) -> dict:
    """Get municipalities covered by test addresses.

    Returns dict mapping municipality -> list of (provider, postal_code) tuples.
    """

    with open(index_path, "rb") as f:
        index = pickle.load(f)

    covered = {}
    for addr in addresses:
        postal_code = addr["postal_code"].replace(" ", "").upper()
        provider = addr["provider"]
        municipality = index.get(postal_code)

        if municipality:
            if municipality not in covered:
                covered[municipality] = []
            covered[municipality].append((provider, postal_code))

    return covered


def main():
    """Check municipality coverage of test addresses."""
    parser = argparse.ArgumentParser(
        description="Check municipality coverage of test addresses"
    )
    parser.add_argument(
        "--index-file",
        default="../data/postcode_index.pkl",
        help="Path to postcode index file (default: ../data/postcode_index.pkl)",
    )
    parser.add_argument(
        "--show-covered",
        action="store_true",
        help="Show covered municipalities instead of missing ones",
    )
    parser.add_argument(
        "--show-duplicates",
        action="store_true",
        help="Show municipalities with multiple test addresses",
    )
    parser.add_argument(
        "--only-summary",
        action="store_true",
        help="Only show summary statistics, skip detailed lists",
    )
    args = parser.parse_args()

    all_municipalities = get_all_municipalities(args.index_file)
    covered = get_covered_municipalities(TEST_ADDRESSES, args.index_file)

    covered_municipalities = set(covered.keys())
    missing_municipalities = all_municipalities - covered_municipalities

    # Find duplicates (municipalities with multiple test addresses)
    duplicates = {m: addrs for m, addrs in covered.items() if len(addrs) > 1}

    # Prepare output
    output_lines = []
    output_lines.append("# Municipality Coverage Report\n")
    output_lines.append(f"Total municipalities in NL: {len(all_municipalities)}")
    output_lines.append(f"Covered by tests: {len(covered_municipalities)}")
    output_lines.append(f"Missing from tests: {len(missing_municipalities)}")
    output_lines.append(f"Duplicates (multiple tests): {len(duplicates)}")
    output_lines.append(
        f"Coverage: {len(covered_municipalities) / len(all_municipalities) * 100:.1f}%"
    )
    if args.only_summary:
        output_text = "\n".join(output_lines)
        LOGGER.info(output_text)
        return

    output_lines.append("")

    if args.show_duplicates:
        output_lines.append(
            f"## Municipalities with multiple test addresses ({len(duplicates)})\n"
        )
        for municipality in sorted(duplicates.keys()):
            providers = duplicates[municipality]
            output_lines.append(f"\n{municipality} ({len(providers)} test addresses)")
            for provider, postal_code in providers:
                output_lines.append(f"  - {provider:30s} {postal_code}")
    elif args.show_covered:
        output_lines.append(
            f"## Covered municipalities ({len(covered_municipalities)})\n"
        )
        for municipality in sorted(covered_municipalities):
            providers = covered[municipality]
            output_lines.append(f"\n{municipality}")
            for provider, postal_code in providers:
                output_lines.append(f"  - {provider:30s} {postal_code}")
    else:
        output_lines.append(
            f"## Missing municipalities ({len(missing_municipalities)})\n"
        )
        output_lines.extend([f"- {m}" for m in sorted(missing_municipalities)])

    output_text = "\n".join(output_lines)
    LOGGER.info(output_text)


if __name__ == "__main__":
    sys.exit(main())
