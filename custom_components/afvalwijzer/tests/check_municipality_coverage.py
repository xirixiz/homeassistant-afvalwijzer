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
from pathlib import Path
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
        "--export",
        default="../data/coverage_report.txt",
        metavar="FILE",
        help="Export report to file instead of stdout",
    )
    args = parser.parse_args()

    LOGGER.info("Loading municipality data...")
    all_municipalities = get_all_municipalities(args.index_file)
    covered = get_covered_municipalities(TEST_ADDRESSES, args.index_file)

    covered_municipalities = set(covered.keys())
    missing_municipalities = all_municipalities - covered_municipalities

    # Find duplicates (municipalities with multiple test addresses)
    duplicates = {m: addrs for m, addrs in covered.items() if len(addrs) > 1}

    # Prepare output
    output_lines = []
    output_lines.append("=" * 70)
    output_lines.append("MUNICIPALITY COVERAGE REPORT")
    output_lines.append("=" * 70)
    output_lines.append(f"Total municipalities in NL: {len(all_municipalities)}")
    output_lines.append(f"Covered by tests: {len(covered_municipalities)}")
    output_lines.append(f"Missing from tests: {len(missing_municipalities)}")
    output_lines.append(f"Duplicates (multiple tests): {len(duplicates)}")
    output_lines.append(
        f"Coverage: {len(covered_municipalities) / len(all_municipalities) * 100:.1f}%"
    )
    output_lines.append("=" * 70)
    output_lines.append("")

    if args.show_duplicates:
        output_lines.append(
            f"MUNICIPALITIES WITH MULTIPLE TEST ADDRESSES ({len(duplicates)}):"
        )
        output_lines.append("-" * 70)
        for municipality in sorted(duplicates.keys()):
            providers = duplicates[municipality]
            output_lines.append(f"\n{municipality} ({len(providers)} test addresses)")
            for provider, postal_code in providers:
                output_lines.append(f"  - {provider:30s} {postal_code}")
    elif args.show_covered:
        output_lines.append(f"COVERED MUNICIPALITIES ({len(covered_municipalities)}):")
        output_lines.append("-" * 70)
        for municipality in sorted(covered_municipalities):
            providers = covered[municipality]
            output_lines.append(f"\n{municipality}")
            for provider, postal_code in providers:
                output_lines.append(f"  - {provider:30s} {postal_code}")
    else:
        output_lines.append(f"MISSING MUNICIPALITIES ({len(missing_municipalities)}):")
        output_lines.append("-" * 70)
        output_lines.extend(sorted(missing_municipalities))

    # Add duplicates section when exporting
    if args.export and duplicates:
        output_lines.append("")
        output_lines.append("=" * 70)
        output_lines.append(
            f"MUNICIPALITIES WITH MULTIPLE TEST ADDRESSES ({len(duplicates)}):"
        )
        output_lines.append("=" * 70)
        for municipality in sorted(duplicates.keys()):
            providers = duplicates[municipality]
            output_lines.append(f"\n{municipality} ({len(providers)} test addresses)")
            for provider, postal_code in providers:
                output_lines.append(f"  - {provider:30s} {postal_code}")

    # Output to file or stdout
    output_text = "\n".join(output_lines)

    if args.export:
        Path(args.export).write_text(output_text + "\n")
        LOGGER.info("Report exported to %s", args.export)
    else:
        LOGGER.info(output_text)

    return 0 if len(missing_municipalities) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
