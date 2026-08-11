# Contributing

Thanks for helping out. This document covers local development and, for
maintainers, how to cut a release.

For bug reports and feature requests, see [SUPPORT.md](.github/SUPPORT.md)
instead.

## Getting started

### Dev container (recommended)

Open the repository in VS Code and reopen in the container. Setup runs
automatically and you are done.

### Local checkout

```bash
git clone https://github.com/xirixiz/homeassistant-afvalwijzer.git
cd homeassistant-afvalwijzer
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt -r requirements_test.txt
pre-commit install
```

This is the same set of Python packages CI installs, and it is enough to run the
test suite.

## Day-to-day scripts

Everything you need is already in `scripts/`:

| Script | Purpose |
| --- | --- |
| `scripts/test` | Run the test suite (`pytest tests`) |
| `scripts/coverage` | Tests plus coverage and `pytest.xml`, which is what CI runs |
| `scripts/test-module` | Run a single module against the live providers |
| `scripts/check-municipality-coverage` | Check which municipalities are covered |
| `scripts/lint` | `ruff check . --fix` |
| `scripts/develop` | `docker compose up` to run Home Assistant locally with the component mounted |
| `scripts/upgrade` | Upgrade to the latest (pre-release) Home Assistant |
| `scripts/dev-branch` | Install Home Assistant from its `dev` branch |
| `scripts/specific-version` | Pin a specific Home Assistant version |

`.pre-commit-config.yaml` runs ruff check and ruff format, and normalises JSON
in `manifest.json`, `hacs.json`, `strings.json`, and the translation files. Hand
edited JSON will be reformatted on commit, so let the hook win rather than
fighting it.

## What CI enforces

`.github/workflows/ci.yml` runs on every pull request, on pushes to `main`, and
on tags:

- hassfest and the HACS action (`category: integration`)
- `ruff check`
- `scripts/coverage`

## Versioning scheme

Versions are CalVer with a sequence number:

- stable: `YYYY.SEQ`, for example `2026.1019`
- beta: `YYYY.SEQ.0bN`, for example `2026.1019.0b1`

The sequence starts at `1000` each calendar year and only ever increases within
that year. The grammar lives in `VERSION_RE` in `update_version.py`.

The `.0b` spelling is load bearing. Home Assistant and HACS compare versions
with AwesomeVersion, which rejects the retired `2026.1019-b01` form outright and
parses `2026.1019b1` without recognising it as a pre-release. Only `.0bN` is
both parseable and correctly flagged as a beta.

Ordering rule worth internalising: **a beta sorts below its own stable
release.** Once `2026.1019` has shipped, `2026.1019.0b2` is in the past and can
never be released. If you need another beta after a stable, open the next
sequence.

`tests/test_version_scheme.py` cross-checks this scheme against AwesomeVersion,
so if you change the grammar, that is the test that will tell you.

## Cutting a release (maintainers)

1. Make sure `main` is green and up to date.

2. Bump the version:

   ```bash
   python3 update_version.py --beta          # next beta
   python3 update_version.py                 # next stable
   python3 update_version.py --set 2026.1020 # explicit version
   ```

   A stable bump *promotes* an in-progress beta to its final version rather than
   skipping a sequence: with `2026.1019.0b3` in the manifest, a plain
   `update_version.py` produces `2026.1019`.

   This rewrites both `custom_components/afvalwijzer/manifest.json` and
   `custom_components/afvalwijzer/const/const.py`. Both must carry the version,
   which is why the script is the only sanctioned way to bump.

3. Commit both files. The existing convention is:

   ```bash
   git commit -am "Prepare release 2026.1019.0b1"
   ```

4. Dry-run the release gate locally before pushing anything:

   ```bash
   scripts/verify-version 2026.1019.0b1
   ```

   It prints `Version OK: <tag>` when the tag is well formed, matches both
   files, and is newer than every existing release tag.

5. Tag and push. No `v` prefix: the workflow matches the tag against the version
   grammar and compares it to the manifest verbatim, so a `v`-prefixed tag is
   silently ignored.

   ```bash
   git push origin main
   git tag 2026.1019.0b1
   git push origin 2026.1019.0b1
   ```

6. `.github/workflows/release.yml` takes over: it re-runs
   `scripts/verify-version`, zips `custom_components/afvalwijzer` into
   `afvalwijzer.zip`, and publishes a GitHub release with generated notes.
   A tag ending in `bN` is published as a pre-release, everything else as a
   stable release.

The workflow only triggers on tags matching the version grammar, so unrelated
tags are ignored rather than starting a release attempt. The flip side is that a
malformed tag does nothing at all: if you push `v2026.1020` or `2026.1020-b01`
and no workflow run appears, the tag name is why. Check the tag before assuming
the release is queued.

### When a release fails verification

`scripts/verify-version` refuses to release rather than publishing something
broken. It reports one of:

- the tag is not a valid version
- `manifest.json` or `const.py` does not match the tag
- the tag is not newer than an existing release

To recover, delete the tag and retag after fixing the version:

```bash
git push --delete origin 2026.1019.0b1
git tag -d 2026.1019.0b1
python3 update_version.py --set <correct version>
git commit -am "Prepare release <correct version>"
git push origin main
git tag <correct version>
git push origin <correct version>
```

Recreating the *same* tag after a fix is fine: the check excludes the tag being
released from the "is it newer" comparison. Tags from older schemes (`5.3.3`,
the retired `-bNN` betas) do not parse and are skipped entirely.
