#!/usr/bin/env python3
"""Afvalwijzer integration."""

import argparse
from datetime import date
import json
import logging
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = REPO_ROOT / "custom_components/afvalwijzer/manifest.json"
CONST_PATH = REPO_ROOT / "custom_components/afvalwijzer/const/const.py"

# YYYY.SEQ for a stable release, YYYY.SEQ.0bN for a beta. The ".0b" form is
# what AwesomeVersion (used by HA and HACS) parses as a CalVer pre-release:
# "2026.1019-b01" is rejected outright and raises when compared, and
# "2026.1019b1" parses but is not recognised as a beta.
VERSION_RE = re.compile(r"^(?P<year>\d{4})\.(?P<seq>\d{4,})(?:\.0b(?P<beta>\d+))?$")
VERSION_ASSIGN_RE = re.compile(r'VERSION\s*=\s*"(?P<version>[^"]+)"')

FIRST_SEQ = 1000


def sort_key(version: str) -> tuple[int, int, float]:
    """Return an ordering key for a version in this scheme.

    A stable release sorts above every beta of the same sequence number, which
    is why an already-released sequence can never be re-opened as a beta. This
    mirrors AwesomeVersion's ordering without needing it as a dependency; see
    tests/test_version_scheme.py for the cross-check.
    """
    match = VERSION_RE.match(version)
    if not match:
        raise ValueError(f"not a recognised version: {version!r}")
    beta = match.group("beta")
    return (
        int(match.group("year")),
        int(match.group("seq")),
        int(beta) if beta else float("inf"),
    )


def compute_next_version(current_version: str | None, *, beta: bool = False) -> str:
    """Compute the next version string based on the current date and version.

    A beta bumps the beta counter when one is already in progress, otherwise it
    opens a beta for the next sequence number. A stable release promotes an
    in-progress beta to its final version rather than skipping a sequence.
    """
    current_year = date.today().year

    if not current_version:
        parsed = None
    else:
        match = VERSION_RE.match(current_version.strip())
        if not match:
            # Refuse rather than silently restarting the sequence: resetting to
            # FIRST_SEQ would move the version backwards and ship an update
            # nobody can install over the top of.
            raise ValueError(
                f"Unrecognised current version {current_version!r}; "
                "expected YYYY.SEQ or YYYY.SEQ.0bN"
            )
        parsed = match

    if parsed is None or int(parsed.group("year")) != current_year:
        return (
            f"{current_year}.{FIRST_SEQ}.0b1" if beta else f"{current_year}.{FIRST_SEQ}"
        )

    seq = int(parsed.group("seq"))
    current_beta = int(parsed.group("beta")) if parsed.group("beta") else None

    if beta:
        if current_beta is not None:
            return f"{current_year}.{seq}.0b{current_beta + 1}"
        return f"{current_year}.{seq + 1}.0b1"

    if current_beta is not None:
        return f"{current_year}.{seq}"
    return f"{current_year}.{seq + 1}"


def _write_version(new_version: str) -> str | None:
    """Write `new_version` to the manifest and const module, returning the old one."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    old_version = str(manifest.get("version", "")).strip() or None

    if manifest.get("version") != new_version:
        manifest["version"] = new_version
        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    const_text = CONST_PATH.read_text(encoding="utf-8")

    if VERSION_ASSIGN_RE.search(const_text):
        new_const_text = VERSION_ASSIGN_RE.sub(f'VERSION = "{new_version}"', const_text)
    else:
        new_const_text = const_text.rstrip() + f'\n\nVERSION = "{new_version}"\n'

    if new_const_text != const_text:
        CONST_PATH.write_text(new_const_text, encoding="utf-8")

    return old_version


def main() -> None:
    """Update version numbers in manifest.json and const.py."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--beta",
        action="store_true",
        help="cut a beta (YYYY.SEQ.0bN) instead of a stable release",
    )
    group.add_argument(
        "--set",
        dest="explicit",
        metavar="VERSION",
        help="set an explicit version instead of computing the next one",
    )
    args = parser.parse_args()

    if args.explicit:
        if not VERSION_RE.match(args.explicit.strip()):
            parser.error(
                f"Invalid version {args.explicit!r}; expected YYYY.SEQ or YYYY.SEQ.0bN"
            )
        new_version = args.explicit.strip()
    else:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        current = str(manifest.get("version", "")).strip() or None
        new_version = compute_next_version(current, beta=args.beta)

    old_version = _write_version(new_version)

    LOGGER.info("Updated version from %s to %s", old_version, new_version)


if __name__ == "__main__":
    main()
